# Strategy 编写规范与 Alpaca Paper Trading

## 1. 架构

```mermaid
flowchart LR
    subgraph S["strategy/策略名"]
        RM["README.md<br/>策略卡片"]
        DATA["data.py<br/>从 Sharadar SEP 下载数据"]
        CFG["config.yaml<br/>资产集、调仓频率、参数<br/>paper 块：账户、资金、风控上限、开关"]
        WGT["weights.py<br/>数据 → 目标权重"]
    end

    subgraph RUN["src/fbs/live · rebalance：runner.py 的 rebalance 按 1→6 调用"]
        L1["1 读取并校验策略文件夹<br/>loader.py"]
        L2["2 判断今天是否调仓<br/>plan.py"]
        L3["3 下载数据、算信号日 t 的权重<br/>策略的 data.py、weights.py"]
        L4["4 交易前检查<br/>checks.py"]
        L5["5 权重 → 整股订单<br/>plan.py"]
        L6["6 写记录；dry run 生成 Dry-run 报告，--submit 提交收盘市价单<br/>report.py、broker.py"]
    end

    subgraph PERF["src/fbs/live · performance：runner.py 的 performance"]
        P1["实盘收益 vs 同期回测、成交质量<br/>report.py"]
    end

    VD{{"Sharadar SEP"}}
    AP{{"Alpaca<br/>Paper Trading API"}}
    REC[("records/<br/>每次运行的 JSON 记录")]
    DRY[["Dry-run 报告<br/>records/运行名.pdf<br/>上线前：判断能否上线"]]
    LIVE[["实盘报告<br/>records/日期-performance.pdf<br/>上线后：评估表现、修订策略"]]

    CFG --> L1
    L1 --> L2 --> L3 --> L4 --> L5 --> L6
    L3 -->|"调用"| DATA
    L3 -->|"调用"| WGT
    DATA -->|"下载"| VD
    L4 & L5 -->|"账户、持仓、价格"| AP
    L6 -->|"--submit：MOC 订单"| AP
    L6 --> REC
    L6 -->|"dry run"| DRY
    L4 -->|"任何一项不通过：不下单"| REC
    REC -->|"首次 --submit 的执行日"| P1
    AP -->|"账户净值、成交"| P1
    P1 --> LIVE
```

入口是 `python -m fbs.live 命令 策略名`（`__main__.py`）。`rebalance` 由 `runner.py` 的 `rebalance` 依次执行：

| 步骤 | 文件 | 函数 | 做什么 |
| --- | --- | --- | --- |
| 1 | loader.py | `load_strategy` | 读 config.yaml（含 paper 块），检查必填字段，导入 data.py 和 weights.py |
| 2 | runner.py、plan.py | `_pick_sessions`、`rebalance_sessions` | 从 Alpaca 取交易日历，定出信号日 t 和执行日 t+1；信号日不是调仓日就结束 |
| 3 | runner.py、策略的 data.py、weights.py | `_target_weights`、`fetch`、`compute` | 下载最近 lookback_sessions 天的数据，取信号日那一行权重 |
| 4 | checks.py | `check_data`、`check_weights`、`check_account`、`check_orders` | 数据是否最新、权重是否超风控上限、账户是否正常；`check_orders` 在第 5 步算出订单后检查订单数、金额和换手率；任何一项不通过就不下单 |
| 5 | runner.py、plan.py | `_plan`、`clean_targets`、`plan_orders`、`turnover` | 去掉不能交易的股票，按账户持仓和最新价算出整股买卖数量，先卖后买 |
| 6 | runner.py、report.py、broker.py | `_write_record`、`_write_dry_run_report`、`write_dry_run_report`、`_submit`、`submit_moc` | 每次运行写 records/ 记录；不加 --submit 时生成 Dry-run 报告；加 --submit 时提交收盘市价单 |

`performance` 由 `runner.py` 的 `performance` 执行：从 records/ 找到第一次 --submit 的执行日，从 Alpaca 取账户净值和订单成交，用同一段时间的数据重跑回测，调用 report.py 生成实盘报告。

broker.py 是唯一连接 Alpaca 的文件，账户、持仓、价格、下单、净值和成交都通过它。

## 2. 新建一个策略

1. 复制 strategy_template 文件夹，改名为策略名（小写字母加下划线）；策略名就是文件夹名，命令行里也用它
2. data.py：已写好，一般不用改。universe 的 Sharadar SEP 日线保存在策略自己的 data/（不提交到 git）：第一次运行下载全部历史，之后每次只增量下载新的交易日和被修订（拆股、分红调整）的历史行；删掉 data/sync_state.json 可重新全量下载，详见 data/README.md
3. 按顺序修改 config.yaml 的研究部分（每项的含义见文件内注释；策略只有这一个配置文件）：

   | 顺序 | 参数 | 填什么 |
   | --- | --- | --- |
   | 1 | universe | 可交易的股票代码 |
   | 2 | rebalance | D 每天 / W 每周最后一个交易日 / M 每月最后一个交易日 |
   | 3 | lookback_sessions | 因子需要数据最长窗口 + 余量 |
   | 4 | backtest_start | Dry-run 报告的回测起始日 |
   | 5 | split | 样本划分：is_end 是 IS 最后一天，embargo_sessions 是 Embargo 的交易日数（不短于一个调仓周期：D 1 / W 5 / M 21），之后是 OOS |
   | 6 | params | weights.py 用到的全部参数，只按 IS 的结果选，不按 OOS 改 |
   | 7 | data.field | 传给 weights.py 的价格列，常用 close_adj |

4. 写 weights.py 的 compute：

   ```python
   def compute(data, params):
   ```

   | | 内容 |
   | --- | --- |
   | 输入 data | data.py 的输出：行是交易日（升序），列是 universe 的股票代码，值是 data.field（如 close_adj） |
   | 输入 params | config.yaml 的 params，参数一律从这里取，不写死在代码里 |
   | 输出 | 与 data 相同的行和列，值是目标权重 = 占策略资金的比例；做多为正、做空为负、不持有为 0 |

   按四步写，每步写一行注释、一两行代码（完整示例见 strategy_example/weights.py）：

   1. 信号：每只股票每天一个分数，例如 `data.shift(skip) / data.shift(lookback) - 1`
   2. 有效条件：去掉当天无价格或历史不够长的股票，例如 `signal.where(data.notna())`
   3. 选股：按分数排名选出要持有的股票，例如 `signal.rank(axis=1, ascending=False) <= top_n`
   4. 权重：给选中的股票分配权重，例如等权 `selected.div(selected.sum(axis=1), axis=0) * gross`，最后 `fillna(0.0)`

   规则：

   - 第 t 行只能用 t 日收盘及以前的数据：只用 shift、rolling 等向后看的运算，不用全样本均值、标准化或未来数据
   - 每一行都要算：回测用全部行，paper trading 只取信号日那一行；运行器只在 rebalance 指定的日子下单
   - 权重绝对值之和不超过 config.yaml paper.limits 的 max_gross，单只不超过 max_weight；建议留 3%–5% 现金吸收整股取整误差

5. 干跑：`python -m fbs.live rebalance 策略名 --asof YYYY-MM-DD`，不下单，在 records/ 生成 JSON 记录和 Dry-run 报告（目标权重、计划订单、检查结果、回测曲线，指标按 IS、OOS 分开列，OOS 只做报告）；--asof 填过去的一个调仓日
6. 填写策略卡片 README.md，结论引用最新的 Dry-run 报告
7. 上 paper trading 前按顺序修改 config.yaml 的 paper 块：

   | 顺序 | 参数 | 填什么 |
   | --- | --- | --- |
   | 1 | paper.account | Alpaca paper 账户名，.env 中填 ALPACA_账户名_KEY / _SECRET |
   | 2 | paper.capital | 策略资金，不超过账户净值 |
   | 3 | paper.limits | 风控上限，参考 Dry-run 报告中的换手率和持仓再留余量 |
   | 4 | paper.enabled | 先保持 false；干跑核对无误后改为 true |

8. 上线：`python -m fbs.live rebalance 策略名 --submit`，每个调仓日运行
9. 上线后定期运行 `python -m fbs.live performance 策略名`，读实盘报告：实盘与回测的差距、滑点和成交率，据此修订策略
