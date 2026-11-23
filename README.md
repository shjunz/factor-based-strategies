# factor-based-strategies

因子策略研究项目。研究方法见 [research_spec.md](research_spec.md)，各章节对应的代码文件见 [architecture.md](architecture.md)。

## 架构（C4）

图由 [docs/C4_Architecture/workspace.dsl](docs/C4_Architecture/workspace.dsl)（Structurizr DSL）生成。改图只改这个文件，然后运行 `make diagrams` 重新生成 `docs/C4_Architecture/` 下的 SVG。每往下一层，就到对应文件夹的 README 里看。设计细节见 [architecture_new.md](architecture_new.md)。

### L1 系统上下文

![L1 系统上下文](docs/C4_Architecture/L1-context.svg)

Quant Researcher 在本系统里研究因子，并把自研的通用函数移植到 QuantConnect；在 QuantConnect 上用 QC Data 做因子挖掘和策略回测，表现好的策略购买 Oxford Street 的数据，由 Quant Researcher 移植到 `strategy/`。两种回测分工不同：Quant Researcher 负责 QuantConnect 上的回测，Quant Developer 负责本系统上的回测与实盘交易（Alpaca）。

### L2 容器

![L2 容器](docs/C4_Architecture/L2-containers.svg)

箭头表示数据流向，编号是先后顺序：① 在本系统研究、评价因子 → ② 把自研的通用函数移植到 QuantConnect → ③ QuantConnect 取 QC Data → ④ 在 QuantConnect 做因子挖掘、策略回测 → ⑤ 表现好的策略购买数据 → ⑥ 移植策略 → ⑦ Quant Developer 做回测与实盘交易 → ⑧ 启动策略包 → ⑨–⑫ 缺数据时增量下载、写入、读取 → ⑬ 返回每日权重 → ⑭ GET 账户、持仓和时钟 → ⑮ 先回测（rebalance 的第一道门槛）→ ⑯ 回测报告 PDF 写入运行记录（回测算不出来就整次停下）→ ⑰ 回测通过，Pre-trade 风控检查数据、调仓权重、账户 → ⑱ 通过检查的调仓权重进入订单执行 → ⑲ 整股订单回到 Pre-trade 检查订单数、金额、换手 → ⑳ 通过检查的订单 → ㉑ 订单执行 POST 收盘市价单（干跑跳过）→ ㉒ 写运行记录 JSON；收盘后定时运行 performance：㉓ Post-trade 风控 GET 成交、收盘价、净值 → ㉔ 实盘报告 PDF 写入运行记录 → ㉕ 运行记录回到实盘交易（performance 找上线日；IBKR 的订单和净值账本供下次调仓去重）。L1 图上的编号和这里一致。API 箭头：GET 从 API 指向读取方，POST 从发送方指向 API。

### 各容器的 README

| 容器 | 类型 | 代码 | L3 / L4 在哪看 |
| --- | --- | --- | --- |
| 策略包 | 每个策略一个，被 live 和回测加载 | `strategy/{name}/` | [strategy/README.md](strategy/README.md) |
| 数据下载 | 由策略的 data.py 调用 | `src/fbs/etl/` | [src/fbs/etl/README.md](src/fbs/etl/README.md) |
| 回测 | 被 live 的报告调用 | `src/fbs/backtesting/` | [src/fbs/backtesting/README.md](src/fbs/backtesting/README.md) |
| 实盘交易 | 命令行，AWS 上定时运行 | `src/fbs/live/` | [src/fbs/live/README.md](src/fbs/live/README.md)（含一次 rebalance 的流程图和 AWS 部署图） |
| 风控 | 共享库 | `src/fbs/risk/` | [src/fbs/risk/README.md](src/fbs/risk/README.md) |
| 订单执行 | 共享库 | `src/fbs/execution/` | [src/fbs/execution/README.md](src/fbs/execution/README.md) |
| 策略研究 | 研究用的函数库 | `src/fbs/research/` | [src/fbs/research/README.md](src/fbs/research/README.md) |

图中灰色虚线的框和箭头是已经设计、还没实现的部分（architecture_new.md §5.15）。

### 准备

根据系统选一种，按顺序执行。

依赖由 [uv](https://docs.astral.sh/uv/) 管理：[pyproject.toml](pyproject.toml) 声明需要哪些包，[uv.lock](uv.lock) 锁定每个包的确切版本，所以每个人装出来的环境完全一样。Python 3.12 也由 uv 自动下载，不需要自己装。

#### macOS / Linux

```bash
# 0. 安装 uv（只需一次）
brew install uv          # 没有 Homebrew 时：curl -LsSf https://astral.sh/uv/install.sh | sh

# 1. 按 uv.lock 创建虚拟环境 .venv，安装 fbs 包和全部依赖（含 live 下单依赖）
make install

# 2. 生成 .env，再打开 .env 填入 API key（等号两边不要有空格）
make env

# 3. 用示例策略干跑一次：下载数据、算权重、生成计划订单和报告，不下单
.venv/bin/python -m fbs.live rebalance strategy_example --asof 2026-10-30
```

#### Windows

在 VS Code 里按 `` Ctrl+` `` 打开终端，默认就是 PowerShell。

```powershell
# 0. 安装 uv（只需一次），装完重开终端
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# 1. 按 uv.lock 创建虚拟环境 .venv，安装 fbs 包和全部依赖（含 live 下单依赖）
uv sync --locked --extra live

# 2. 生成 .env
if (Test-Path .env) { ".env already exists, left unchanged" } else { Set-Content .env "NASDAQ_DATA_LINK_API_KEY=" -Encoding ascii }

# 3. 打开 .env 填入 API key（等号两边不要有空格）

# 4. 用示例策略干跑一次：下载数据、算权重、生成计划订单和报告，不下单
.venv\Scripts\python -m fbs.live rebalance strategy_example --asof 2026-10-30
```

不需要激活虚拟环境（`activate`），直接用 `.venv\Scripts\` 下的程序即可，这样也避开了 PowerShell 默认禁止运行脚本的限制。

`.env` 里要填的 key：

| 变量 | 谁用 | 什么时候需要 |
|---|---|---|
| `NASDAQ_DATA_LINK_API_KEY` | [fbs.etl](src/fbs/etl/README.md) 下载 Sharadar 数据 | 一开始就要 |
| `ALPACA_账户名_KEY`、`ALPACA_账户名_SECRET` | [fbs.live](src/fbs/live/README.md) 连接 Alpaca paper 账户，账户名是策略 config.yaml 的 `paper.account` | 干跑和 paper trading（干跑也会读真实账户） |

AWS 上不用 `.env`，key 存在 Secrets Manager，作为环境变量注入。干跑的结果在 `strategy/strategy_example/records/`；新建策略、paper trading 和上线的步骤见 [strategy/README.md](strategy/README.md)。

## 常用命令

`make help` 列出全部命令。

| 命令 | 作用 |
|---|---|
| `make install` | 按 `uv.lock` 创建或同步 `.venv`，装上 fbs 包和全部依赖；pull 到新的 `uv.lock` 后再跑一次即可同步 |
| `uv add 包名` | 新增依赖：同时改 `pyproject.toml` 和 `uv.lock`，两个文件一起提交 |
| `make lock` | 手动改了 `pyproject.toml` 后，重新生成 `uv.lock` |
| `make upgrade` | 把所有包升级到允许范围内的最新版，重写 `uv.lock` 并同步 `.venv` |
| `make env` | 生成只含 `NASDAQ_DATA_LINK_API_KEY=` 一行的 `.env`，已存在时不覆盖 |
| `python -m fbs.live 命令 策略名` | 实盘交易：`rebalance`、`status`、`performance`、`halt`、`flatten`，见 [src/fbs/live/README.md](src/fbs/live/README.md) |
| `python -m fbs.etl.provider.sharadar.pipeline` | 把 `data/bronze/` 下的 SEP 清洗成 `data/gold/`，见 [src/fbs/etl/README.md](src/fbs/etl/README.md) |
| `make diagram-tools` | 下载画 C4 图的工具（Structurizr CLI、PlantUML），每台机器一次，需要 Java |
| `make diagrams` | 由 `docs/C4_Architecture/workspace.dsl` 重新生成 C4 图 SVG |
| `make data-diagrams` | 由 `docs/Data_architecture/*.puml` 重新生成数据架构图 SVG |
| `make clean-bronze` | 删除 `data/bronze/` 中的全部下载数据，执行前需要输入 `y` 确认 |
| `make clean` | 删除 `.venv` 和构建产物，之后需要重新 `make install` |

Windows 下对应的 PowerShell 命令：

| 对应 | PowerShell 命令 |
|---|---|
| `make install` | `uv sync --locked --extra live` |
| `make lock` | `uv lock` |
| `make upgrade` | `uv lock --upgrade`，再 `uv sync --locked --extra live` |
| `make env` | `if (Test-Path .env) { ".env already exists, left unchanged" } else { Set-Content .env "NASDAQ_DATA_LINK_API_KEY=" -Encoding ascii }` |
| `python -m ...` | 把 `python` 换成 `.venv\Scripts\python` |
| `make clean-bronze` | `if ((Read-Host "Delete everything in data/bronze? [y/N]") -eq 'y') { Get-ChildItem data\bronze \| Remove-Item -Recurse -Force }` |
| `make clean` | `Remove-Item -Recurse -Force .venv, build, dist, src\*.egg-info -ErrorAction SilentlyContinue`，再 `Get-ChildItem -Recurse -Directory -Filter __pycache__ \| Remove-Item -Recurse -Force` |

## 目录

| 目录 | 内容 |
|---|---|
| `src/fbs/etl/` | 数据下载：抽取、代码映射、格式统一、写入（[README](src/fbs/etl/README.md)） |
| `src/fbs/factor/` | 因子算子：`delay`、`ts_mean`、`ts_spearman` 等时间序列和逐元素运算 |
| `src/fbs/sample/` | 样本构建：前向收益、波动率调整收益 |
| `src/fbs/backtesting/` | 回测（[README](src/fbs/backtesting/README.md)） |
| `src/fbs/live/` | 实盘交易：Alpaca paper trading（[README](src/fbs/live/README.md)） |
| `src/fbs/risk/` | 风控（[README](src/fbs/risk/README.md)） |
| `src/fbs/execution/` | 执行：调仓日、订单（[README](src/fbs/execution/README.md)） |
| `src/fbs/research/` | 策略研究：`eval/` 因子评价、`combination_factor/` 因子组合（[README](src/fbs/research/README.md)） |
| `strategy/` | 每个策略一个文件夹（[README](strategy/README.md)） |
| `docs/C4_Architecture/` | C4 架构图：`workspace.dsl` 和生成的 SVG |
| `docs/Data_architecture/` | 数据架构：实体关系、数据字典、S3 布局、JSON Schema、生命周期（[README](docs/Data_architecture/README.md)） |
| `data/bronze/`、`data/silver/`、`data/gold/` | 仓库共享的原始数据、中间数据、清洗数据，只保存在本地；策略自己的数据在 `strategy/{name}/data/` |
