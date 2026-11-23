/*
 * factor-based-strategies - C4 model (Structurizr DSL)
 *
 * Source of every diagram in docs/C4_Architecture/. Edit this file, then run
 *     make diagrams
 * to regenerate the SVGs (Structurizr CLI -> PlantUML -> SVG).
 *
 * Views (file name = view key; L = C4 level):
 *   L1-context            people, this system, external systems
 *   L2-containers         runnable parts, shared libraries, data stores
 *   L2-deployment-alpaca  AWS scheduled run of the live runner, paper.broker: alpaca
 *   L2-deployment-ibkr    same, paper.broker: ibkr (adds the always-on IB Gateway service)
 *   L3-<container>        one per container, one component per .py file
 *   L3-live-rebalance     one `fbs.live rebalance` run, as a sequence diagram
 *   L4 (code) is not drawn here: see the function tables in each src/fbs/<package>/README.md
 *
 * Conventions:
 *   Boxes are named by what they do, never by file name; file and function names go on the arrows.
 *   Tag "Library" = shared code, never run on its own (dashed border).
 *   Tag "Planned" = designed in architecture_new.md §5.15, not built yet (grey, dashed).
 */
workspace "factor-based-strategies" "因子策略研究与实盘平台" {

    model {

        # ---------------------------------------------------------------- people
        qr = person "Quant Researcher" "因子挖掘、策略研究；在 QuantConnect 上回测；把表现好的策略移植进 factor-based-strategies"
        qd = person "Quant Developer" "开发、运维平台；在 factor-based-strategies 上回测与实盘交易"

        # ------------------------------------------------------ external systems
        qc = softwareSystem "QuantConnect" "策略研究与 QC paper trading" "External"
        dp = softwareSystem "Oxford Street Data Provider API" "行情与基本面数据，例如 Nasdaq Data Link（Sharadar）" "External"
        qcData = softwareSystem "QuantConnect External Data Provider API" "QuantConnect 平台上的数据（QC Data）" "External"
        broker = softwareSystem "Broker API" "券商交易接口，例如 IBKR、Alpaca；现在 paper，之后 live" "External"

        # ----------------------------------------------------------- the system
        fbs = softwareSystem "factor-based-strategies" "数据下载 · 回测 · 实盘交易" {

            strategy = container "策略包" "每个策略一个文件夹、一个券商账户：配置、取数、算权重" "Python package" {
                config = component "策略配置" "资产集、调仓频率、回看长度、样本划分、参数、风控上限" "YAML"
                dataPy = component "数据获取" "fetch(config, start, end)：增量下载并返回价格表" "Python"
                weightsPy = component "权重计算" "compute(data, params)：每个交易日的目标权重" "Python"
            }

            etl = container "数据下载" "从数据商下载原始数据（bronze），统一格式后存成清洗数据（gold）" "Python package" {
                providerMeta = component "供应商元数据" "每个数据商一份：API 代码、key 的变量名、字段映射、数据字典快照" "YAML, CSV"
                extract = component "数据抽取" "每个数据商一个子包：按表和过滤条件下载，读取已下载的文件" "Python"
                identifiers = component "代码映射" "数据商专属：给每行加上 instrument_id" "Python"
                unify = component "格式统一" "字段名改成标准名，日期换成收盘时间戳" "Python"
                loading = component "清洗数据写入" "检查主键唯一，写 Parquet 和同名 .json" "Python"
                pipeline = component "清洗流程" "数据商专属：把抽取、代码映射、格式统一、写入串起来" "Python"
                paths = component "存储路径" "bronze、gold 的目录和文件名规则" "Python"
            }

            backtesting = container "回测" "每次 rebalance 的第一步：回测每日权重、写回测报告；算不出来就整次停下" "Python package" {
                engine = component "回测引擎" "t 日信号、t+1 收盘成交、t+2 起计收益" "Python"
                perf = component "绩效指标" "年化收益、波动、Sharpe、最大回撤" "Python"
                sampleSplit = component "样本划分" "IS / Embargo / OOS" "Python"
                backtestReport = component "回测报告" "PDF：回测曲线、回撤、IS / OOS 指标；只有历史回测" "Python, matplotlib"
            }

            live = container "实盘交易" "命令行：rebalance、status、performance、halt" "Python CLI" {
                cli = component "命令行入口" "解析命令和参数" "Python"
                runner = component "运行流程" "每个命令的步骤：rebalance 按顺序调用回测、pre-trade 风控、订单执行；performance 调用 post-trade" "Python"
                loader = component "策略加载" "读取并校验策略配置，导入取数和算权重的代码" "Python"
                brokerPy = component "券商接口" "brokers/：按 paper.broker 选 Alpaca 或 IBKR 适配器，唯一连接券商的地方：账户、持仓、价格、下单" "Python, alpaca-py / ib_async"
            }

            preTradeRisk = container "Pre-trade 风控" "提交订单前：回测通过后检查数据、调仓权重、账户，订单算出后再查整股订单；不通过则整次不下单" "Python library" "Library" {
                dataFreshness = component "数据新鲜度检查" "数据不为空、包含信号日" "Python"
                weightLimits = component "权重上限检查" "gross / net / 单票 / 做空" "Python"
                accountStatus = component "账户状态检查" "账户正常、资金不超过净值" "Python"
                orderLimits = component "订单上限检查" "订单数 / 单笔金额 / 换手率" "Python"
            }

            postTradeRisk = container "Post-trade 风控" "订单提交后，记录整股订单成交情况：收盘后核对成交、写实盘报告" "Python library" "Library" {
                fills = component "成交核对" "每笔订单的成交股数、成交价 vs 收盘价、滑点" "Python"
                liveReport = component "实盘报告" "PDF：实盘 vs 同期回测、跟踪误差、成交质量" "Python, matplotlib"
                drawdown = component "回撤降仓" "实盘回撤超过阈值后按比例降低仓位" "Python" "Planned"
            }

            execution = container "订单执行" "调仓权重如何变成订单并且提交" "Python library" "Library" {
                rebalanceSessions = component "调仓日历" "哪天调仓（D / W / M）" "Python"
                tradableAssets = component "可交易标的过滤" "去掉不能交易或不能做空的股票" "Python"
                orderPlan = component "订单生成" "目标权重 → 整股订单，先卖后买" "Python"
                orderSubmit = component "订单提交" "能否提交（enabled、开盘、MOC 截止前）；按 client_order_id 去重提交。计划：订单类型从 config 读、临时错误重试" "Python"
                costEstimate = component "成本估算" "下单前估算每笔订单的成本" "Python" "Planned"
            }

            research = container "策略研究" "研究阶段用的函数，实盘不调用" "Python library" "Library" {
                factorEval = component "因子评价" "Rank IC、分组收益、Fama-MacBeth、IC 衰减、换手、尾部风险" "Python"
                factorCombo = component "因子组合" "多个因子组合成一个信号" "Python" "Planned"
            }

            strategyData = container "策略数据" "下载的原始数据和清洗后的价格表" "Files" "Store"
            records = container "运行记录" "rebalance JSON（干跑和提交同名，mode 区分）；回测报告 PDF（文件名带 IS / OOS 日期）；实盘报告 PDF" "Files" "Store"
        }

        # ------------------------------------------------- L1 relationships
        # Numbers = order of the steps, shared with the L2 container view. No file names at L1 / L2.
        # Arrows show data flow: GET points from the API to the reader, POST from the sender to the API.
        qr -> fbs "① 研究、评价因子"
        fbs -> qc "② 移植自研的通用函数（因子评价等）"
        qcData -> qc "③ GET 行情与基本面数据（QC Data）" "HTTPS / REST"
        qr -> qc "④ 因子挖掘、策略回测（QC Data）"
        qc -> dp "⑤ 表现好的策略：确定并购买它需要的数据"
        qc -> fbs "⑥ 移植表现好的策略（Quant Researcher）"
        qd -> fbs "⑦ 回测与实盘交易" "CLI"
        dp -> fbs "⑩ GET 行情与基本面数据" "HTTPS / REST"
        broker -> fbs "⑭ GET 账户、持仓、最新价、时钟和交易日历 / ㉓ 收盘后 GET 成交、收盘价、净值" "HTTPS / REST"
        fbs -> broker "㉑ POST 收盘市价单" "HTTPS / REST"

        # ------------------------------------------------- L2 relationships
        # Arrows show data flow, numbered in order.
        qr -> research "① 研究、评价因子"
        research -> qc "② 移植自研的通用函数（因子评价等）"
        qc -> strategy "⑥ 移植表现好的策略（Quant Researcher）"
        qd -> live "⑦ 回测与实盘交易" "CLI"
        live -> strategy "⑧ 启动策略包"
        strategy -> etl "⑨ 数据缺失：增量更新策略数据"
        dp -> etl "⑩ GET 行情与基本面数据" "HTTPS / REST"
        etl -> strategyData "⑪ 写入策略数据"
        strategyData -> strategy "⑫ 读取数据"
        strategy -> live "⑬ 返回每日权重"
        broker -> live "⑭ GET 账户、持仓、最新价、时钟和交易日历" "HTTPS / REST"
        live -> backtesting "⑮ 历史价格与每日权重：回测（rebalance 的第一道门槛）"
        backtesting -> records "⑯ 回测报告 PDF（回测算不出来就整次停下，不再往下走）"
        backtesting -> preTradeRisk "⑰ 回测通过：检查数据、信号日调仓权重、账户"
        preTradeRisk -> execution "⑱ 通过检查的调仓权重"
        execution -> preTradeRisk "⑲ 整股订单：检查订单数、金额、换手"
        preTradeRisk -> execution "⑳ 通过检查的整股订单"
        execution -> broker "㉑ POST 收盘市价单（--submit；干跑跳过）" "HTTPS / REST"
        live -> records "㉒ 运行记录 JSON：目标权重、检查结果、计划 / 已提交订单"
        broker -> postTradeRisk "㉓ 收盘后 GET 订单成交、收盘价、账户净值（performance 命令）" "HTTPS / REST"
        postTradeRisk -> records "㉔ 实盘报告 PDF：实盘 vs 同期回测、成交质量"
        records -> live "㉕ rebalance JSON（performance 找上线日）；IBKR 的订单和净值账本（下次调仓去重）"
        backtesting -> preTradeRisk "同一套权重调整（计划）" "" "Planned"
        backtesting -> research "评价指标（计划）" "" "Planned"

        # ------------------------------------------------- L3 relationships
        # Same data flow and step numbers as L1 / L2, one level down; file and function names on the arrows.

        # strategy package: ⑧ load, ⑨-⑫ data, ⑬ weights
        loader -> config "⑧ loader.py 读取并校验 config.yaml"
        loader -> dataPy "⑧ loader.py 导入 data.py"
        loader -> weightsPy "⑧ loader.py 导入 weights.py"
        dataPy -> config "data.py 读 config.yaml：universe、data.field"
        weightsPy -> config "weights.py 用 config.yaml 的 params"
        dataPy -> extract "⑨ 数据缺失：data.py → provider/{provider}/extract.py：download_table、read_table（现在只有 sharadar）"
        dataPy -> unify "data.py → unify.py：rename_fields"
        dataPy -> paths "data.py → paths.py：bronze_path"
        extract -> strategyData "⑪ 写入原始下载 data/bronze/（同名 .json 下载记录）"
        dataPy -> strategyData "⑪ 写入清洗后的价格表 data/gold/"
        strategyData -> dataPy "⑫ data.py 读取 data/ 下的价格表"
        dataPy -> weightsPy "价格表：fetch 的输出传给 compute"
        weightsPy -> runner "⑬ compute：每日权重"

        # etl: ⑩ download
        dp -> extract "⑩ GET 行情与基本面数据（provider/{provider}/extract.py）" "HTTPS / REST"
        extract -> providerMeta "provider/{provider}/metadata/provider.yaml：API 代码、key 的变量名"
        unify -> providerMeta "provider/{provider}/metadata/field_map.csv：标准字段名"
        pipeline -> extract "pipeline.py → extract.py：read_table"
        pipeline -> identifiers "pipeline.py → identifiers.py：add_instrument_id"
        pipeline -> unify "pipeline.py → unify.py：rename_fields、map_date_timestamps"
        pipeline -> paths "pipeline.py → paths.py：gold_path"
        pipeline -> loading "pipeline.py → loading.py：save_clean"

        # live: ⑦ command, ⑧ load, ⑭ broker data, ⑮ start the backtest, ㉒ / ㉕ run records
        cli -> runner "⑦ main → runner.py：rebalance / status / performance / halt"
        runner -> loader "⑧ runner.py → loader.py：load_strategy"
        broker -> brokerPy "⑭ GET 时钟、交易日历、账户、持仓、最新价 / ㉓ 收盘后 GET 成交、收盘价、净值（brokers/）" "HTTPS / REST"
        brokerPy -> runner "⑭ 时钟、交易日历：信号日和执行日"
        runner -> rebalanceSessions "rebalance_sessions.py：execution_rebalance_sessions，不是调仓日就结束"
        runner -> engine "⑮ 历史价格与每日权重 → backtest_engine.py：backtest"
        runner -> records "㉒ 运行记录 JSON：{exec_session}-rebalance.json"
        records -> runner "㉕ rebalance JSON（performance 找上线日）；IBKR 的订单和净值账本（下次调仓去重）"
        brokerPy -> broker "㉑ POST 收盘市价单（brokers/：submit_moc）" "HTTPS / REST"

        # backtesting: ⑯ report, ⑰ gate passed
        engine -> backtestReport "回测收益 → backtest_report.py：write_backtest_report"
        backtestReport -> sampleSplit "backtest_report.py → sample_split.py：split_segments"
        backtestReport -> perf "backtest_report.py → performance_metrics.py：metrics"
        backtestReport -> records "⑯ 回测报告 PDF：{exec_session}-backtest_IS-{起止}_OOS-{起止}.pdf"
        engine -> dataFreshness "⑰ 回测通过：本次数据和信号日权重 → pre_trade/data_freshness.py：risk_input_data"
        engine -> rebalanceSessions "backtest_engine.py → rebalance_sessions.py：同一个调仓日历"
        engine -> drawdown "逐日降仓（计划）" "" "Planned"

        # pre-trade: ⑰ data / weights / account, ⑲ orders back for the order check, ⑳ approved orders
        dataFreshness -> weightLimits "数据通过 → weight_limits.py：risk_weights"
        weightLimits -> accountStatus "权重通过 → account_status.py：risk_account"
        brokerPy -> accountStatus "⑭ 账户状态（brokers/：account）"
        accountStatus -> tradableAssets "⑱ 通过检查的调仓权重 → tradable_assets.py：execution_remove_invalid_assets"
        orderPlan -> orderLimits "⑲ 整股订单和换手 → order_limits.py：risk_orders"
        orderLimits -> orderSubmit "⑳ 通过检查的整股订单 → order_submit.py：execution_submit_gate、execution_submit"

        # execution: ⑱ approved weights in, ㉑ orders out
        brokerPy -> tradableAssets "⑭ 可交易、可做空（brokers/：assets）"
        tradableAssets -> orderPlan "可交易的目标权重 → order_plan.py：execution_plan_orders、execution_turnover"
        brokerPy -> orderPlan "⑭ 持仓、最新价、购买力（brokers/：positions、latest_prices、account）"
        orderSubmit -> brokerPy "㉑ brokers/：orders_with_prefix（去重）、submit_moc"
        orderPlan -> costEstimate "cost_estimate.py（计划）" "" "Planned"

        # post-trade (performance, after the close): ㉓ fills in, ㉔ live report out
        brokerPy -> fills "㉓ 订单成交、收盘价（brokers/：orders_with_prefix、daily_closes）"
        brokerPy -> liveReport "㉓ 账户净值历史（brokers/：equity_history）"
        runner -> liveReport "同期回测收益（runner.py 用 backtest_engine.py 重跑）→ live_report.py：write_live_report"
        fills -> liveReport "每笔成交和滑点：risk_fills、risk_fill_summary"
        liveReport -> perf "live_report.py → performance_metrics.py：metrics"
        liveReport -> backtestReport "live_report.py → backtest_report.py：pdf_table、A4"
        liveReport -> records "㉔ 实盘报告 PDF：{last_session}-live-trading.pdf"

        # eval (research use today): ① ②
        qr -> factorEval "① eval/cs/metrics.py：评价因子（前向收益用 fbs/sample/returns.py）" "Python"
        factorEval -> qc "② 移植自研的通用函数（因子评价等）"
        qr -> factorCombo "combination_factor：组合因子（计划）" "Python" "Planned"

        # ------------------------------------------- deployment (AWS, paper.broker: alpaca)
        # Alpaca = REST + API key: one short-lived task, nothing else runs between trading days.
        deploymentEnvironment "AWS-Alpaca" {
            deploymentNode "Amazon Web Services" "" "AWS" {
                alpacaScheduler = infrastructureNode "EventBridge Scheduler" "每个工作日两次（America/New_York）：15:00 rebalance，16:30 performance" "Amazon EventBridge"
                alpacaSecrets = infrastructureNode "Secrets Manager" "Alpaca 和 Nasdaq 的密钥" "AWS Secrets Manager"

                deploymentNode "ECS Fargate task" "临时容器：开始时从 S3 下载数据，结束时（失败也一样）上传数据和运行记录，然后磁盘清空" "Docker container" {
                    alpacaLive = containerInstance live
                    containerInstance strategy
                    containerInstance etl
                    containerInstance preTradeRisk
                    containerInstance postTradeRisk
                    containerInstance execution
                    containerInstance backtesting
                }

                deploymentNode "Amazon S3" "策略数据和运行记录的长期副本；订单去重和净值历史都在 Alpaca 服务器上，不靠这里" "Amazon S3" {
                    containerInstance strategyData
                    containerInstance records
                }
            }
            deploymentNode "Alpaca" "" "SaaS" {
                softwareSystemInstance broker
            }
            deploymentNode "Nasdaq Data Link" "" "SaaS" {
                softwareSystemInstance dp
            }

            alpacaScheduler -> alpacaLive "15:00 python -m fbs.live rebalance {name} --submit"
            alpacaScheduler -> alpacaLive "16:30 收盘后 python -m fbs.live performance {name}（post-trade）"
            alpacaSecrets -> alpacaLive "注入环境变量 ALPACA_*、NASDAQ_DATA_LINK_API_KEY"
        }

        # --------------------------------------------- deployment (AWS, paper.broker: ibkr)
        # IBKR = TWS API socket to a logged-in IB Gateway: the Gateway is a second, always-on service,
        # and the order / equity ledgers in records/ must round-trip through S3 on every run.
        deploymentEnvironment "AWS-IBKR" {
            deploymentNode "Amazon Web Services" "" "AWS" {
                ibkrScheduler = infrastructureNode "EventBridge Scheduler" "每个工作日两次（America/New_York）：15:00 rebalance，16:30 performance" "Amazon EventBridge"
                ibkrSecrets = infrastructureNode "Secrets Manager" "IBKR 用户名 / 密码（给 Gateway 登录）、Nasdaq 密钥" "AWS Secrets Manager"

                deploymentNode "ECS Fargate task" "临时容器：开始时从 S3 下载 data/ 和 records/ibkr-orders.json、ibkr-equity.csv，结束时（失败也一样）全部上传，然后磁盘清空" "Docker container" {
                    ibkrLive = containerInstance live
                    containerInstance strategy
                    containerInstance etl
                    containerInstance preTradeRisk
                    containerInstance postTradeRisk
                    containerInstance execution
                    containerInstance backtesting
                }

                deploymentNode "ECS Fargate service" "常驻容器（desired count = 1），一直保持登录；每天自动重启，时间设在收盘后、远离 15:00 的运行" "Docker container" {
                    gateway = infrastructureNode "IB Gateway" "IBKR 的无界面登录程序 + IBC 自动填用户名密码 + Xvfb 虚拟显示；只接受 VPC 内网的 API 连接" "IB Gateway, IBC"
                }

                deploymentNode "Amazon S3" "策略数据和运行记录的长期副本；ibkr-orders.json（订单去重）和 ibkr-equity.csv（每日净值）只存在这里，丢了就会重复下单 / 缺净值" "Amazon S3" {
                    containerInstance strategyData
                    containerInstance records
                }
            }
            deploymentNode "Interactive Brokers" "" "SaaS" {
                ibkrServers = infrastructureNode "IBKR 交易服务器" "账户、持仓、行情、订单；真钱账户每周一次要在 IBKR Mobile 上批准登录（2FA）" "IBKR"
            }
            deploymentNode "Nasdaq Data Link" "" "SaaS" {
                softwareSystemInstance dp
            }

            ibkrScheduler -> ibkrLive "15:00 python -m fbs.live rebalance {name} --submit"
            ibkrScheduler -> ibkrLive "16:30 收盘后 python -m fbs.live performance {name}（post-trade）"
            ibkrSecrets -> ibkrLive "注入环境变量 IBKR_*_ACCOUNT_ID / _HOST / _PORT、NASDAQ_DATA_LINK_API_KEY"
            ibkrSecrets -> gateway "注入 IBKR 用户名、密码（IBC 自动登录）"
            ibkrLive -> gateway "⑭ 账户、持仓、最新价、可借券、时钟 / ㉑ 收盘市价单 / ㉓ 成交、收盘价、净值（ib_async）" "TWS API socket（VPC 内网）"
            gateway -> ibkrServers "登录并转发请求和订单" "IBKR 专有协议，出站 TLS"
        }
    }

    views {

        systemContext fbs "L1-context" "L1 系统上下文｜本图步骤：①-⑦、⑩、⑭、㉑、㉓（⑧-⑨、⑪-⑬、⑮-⑳、㉒、㉔-㉕ 在系统内部，见 L2-containers）" {
            include *
            include qcData
            autoLayout lr
        }

        container fbs "L2-containers" "L2 容器｜本图步骤：①-㉕ 全部（箭头 = 数据流向，编号 = 先后顺序）" {
            include *
            exclude "relationship.tag==Planned"
            # implied by component-level calls; L2 shows the numbered data flow instead
            exclude "live -> preTradeRisk"
            exclude "live -> execution"
            exclude "live -> postTradeRisk"
            exclude "execution -> live"
            exclude "backtesting -> execution"
            exclude "postTradeRisk -> backtesting"
            exclude "live -> broker"
            exclude "strategy -> strategyData"
            include qcData
            autoLayout tb
        }

        component live "L3-live" "L3 实盘交易｜本图步骤：⑦ 命令 → ⑧ 加载策略 → ⑬ 每日权重 → ⑭ 券商数据 → ⑮ 回测 → ⑯ 回测报告 / ⑰ Pre-trade → ⑱-⑳ 订单执行 → ㉑ 下单 → ㉒ 运行记录；收盘后 ㉓ 成交 → ㉔ 实盘报告 → ㉕ 读回记录（缺 ⑨-⑫ 取数，见 L3-strategy、L3-etl）" {
            include *
            exclude "relationship.tag==Planned"
            # L3 shows ㉑ / ㉓ through 券商接口, so drop the L2 shortcuts; and code-only dependencies
            exclude "execution -> broker"
            exclude "broker -> postTradeRisk"
            exclude "backtesting -> execution"
            exclude "postTradeRisk -> backtesting"
            autoLayout tb
        }

        component preTradeRisk "L3-risk-pre-trade" "L3 Pre-trade 风控｜本图步骤：⑮ 回测 → ⑰ 数据新鲜度 → 权重上限 → 账户状态（⑭ 账户来自券商接口）→ ⑱ 订单执行；⑲ 整股订单回来 → 订单上限 → ⑳ 订单执行" {
            include *
            exclude "live -> execution"
            exclude "backtesting -> execution"
            exclude "execution -> live"
            autoLayout lr
        }

        component postTradeRisk "L3-risk-post-trade" "L3 Post-trade 风控（收盘后，performance 命令）｜本图步骤：㉓ 券商接口 → 成交核对 → 实盘报告 → ㉔ 运行记录 → ㉕ 实盘交易" {
            include *
            exclude "live -> backtesting"
            exclude "backtesting -> records"
            exclude "live -> records"
            exclude "postTradeRisk -> backtesting"
            autoLayout lr
        }

        component execution "L3-execution" "L3 订单执行｜本图步骤：⑰ 回测 → Pre-trade → ⑱ 可交易标的过滤（⑭ 可交易性）→ 订单生成（⑭ 持仓、价格）→ ⑲ Pre-trade → ⑳ 订单提交 → ㉑ 券商接口" {
            include *
            exclude "relationship.tag==Planned"
            exclude "live -> backtesting"
            autoLayout lr
        }

        component backtesting "L3-backtesting" "L3 回测｜本图步骤：⑮ 运行流程 → 回测引擎 → 回测报告 → ⑯ 运行记录；回测引擎 → ⑰ Pre-trade（输入是 weights.py 的原始每日权重，不经过风控和整股取整）" {
            include *
            exclude "relationship.tag==Planned"
            exclude "live -> execution"
            exclude "live -> preTradeRisk"
            exclude "live -> postTradeRisk"
            exclude "execution -> live"
            exclude "preTradeRisk -> execution"
            exclude "execution -> preTradeRisk"
            exclude "postTradeRisk -> backtesting"
            exclude "live -> records"
            exclude "postTradeRisk -> records"
            exclude "records -> live"
            autoLayout lr
        }

        component etl "L3-etl" "L3 数据下载｜本图步骤：⑨ 策略包请求 → ⑩ GET 数据商 → ⑪ 写入策略数据 → ⑫ 策略包读取" {
            include *
            autoLayout lr
        }

        component strategy "L3-strategy" "L3 策略包｜本图步骤：⑧ 加载 → ⑨ 缺数据时调用数据下载 → ⑪ 写入策略数据 → ⑫ 读取 → ⑬ 每日权重交回实盘交易（⑩ 见 L3-etl）" {
            include *
            autoLayout lr
        }

        component research "L3-research" "L3 策略研究｜本图步骤：① 研究、评价因子 → ② 移植到 QuantConnect；④ Quant Researcher 在 QuantConnect 做因子挖掘、回测（③、⑤、⑥ 见 L1-context、L2-containers）" {
            include *
            autoLayout lr
        }

        dynamic live "L3-live-rebalance" "L3 动态图：一次 python -m fbs.live rebalance {name} [--submit]｜本图步骤：⑦ → ⑧ → ⑭ → ⑨-⑬ → ⑮ → ⑯ / ⑰ → ⑭ → ⑱ → ⑲ → ⑳ → ㉑ → ㉒（㉓-㉕ 在收盘后的 performance，见 L3-live）" {
            cli -> runner "⑦ rebalance(name, submit)"
            runner -> loader "⑧ loader.py：load_strategy，导入 data.py、weights.py"
            broker -> brokerPy "⑭ GET 时钟、交易日历"
            brokerPy -> runner "⑭ 信号日 t、执行日 t+1"
            runner -> execution "rebalance_sessions.py：不是调仓日就结束"
            strategy -> runner "⑨-⑬ data.py fetch（缺数据就增量下载）、weights.py compute：每日权重"
            runner -> backtesting "⑮ backtest_engine.py：回测"
            backtesting -> records "⑯ backtest_report.py：回测报告 PDF；算不出来就停（跳到写 JSON）"
            backtesting -> preTradeRisk "⑰ 回测通过：data_freshness.py、weight_limits.py，不通过就停"
            broker -> brokerPy "⑭ GET 账户、持仓、可交易性、最新价"
            brokerPy -> preTradeRisk "⑭ account_status.py：账户不正常就停"
            preTradeRisk -> execution "⑱ tradable_assets.py、order_plan.py：生成整股订单"
            execution -> preTradeRisk "⑲ order_limits.py：订单超限就停"
            preTradeRisk -> execution "⑳ order_submit.py：能否提交、去重（--submit；干跑到此为止）"
            execution -> brokerPy "㉑ brokers/：submit_moc"
            brokerPy -> broker "㉑ POST 收盘市价单"
            runner -> records "㉒ 运行记录 JSON：{exec_session}-rebalance.json"
            properties {
                "plantuml.sequenceDiagram" "true"
            }
        }

        deployment fbs "AWS-Alpaca" "L2-deployment-alpaca" "L2 部署图：AWS 定时运行，券商 Alpaca｜本图步骤：⑧-㉕（①-⑦ 见 L2-containers）" {
            include *
            exclude "relationship.tag==Planned"
            exclude "live -> preTradeRisk"
            exclude "live -> execution"
            exclude "live -> postTradeRisk"
            exclude "execution -> live"
            exclude "backtesting -> execution"
            exclude "postTradeRisk -> backtesting"
            exclude "live -> broker"
            exclude "strategy -> strategyData"
            autoLayout lr
        }

        deployment fbs "AWS-IBKR" "L2-deployment-ibkr" "L2 部署图：AWS 定时运行，券商 IBKR（多一个常驻 IB Gateway）｜本图步骤：⑧-㉕（①-⑦ 见 L2-containers）" {
            include *
            exclude "relationship.tag==Planned"
            exclude "live -> preTradeRisk"
            exclude "live -> execution"
            exclude "live -> postTradeRisk"
            exclude "execution -> live"
            exclude "backtesting -> execution"
            exclude "postTradeRisk -> backtesting"
            exclude "live -> broker"
            exclude "strategy -> strategyData"
            autoLayout lr
        }

        styles {
            element "Element" {
                color #ffffff
            }
            element "Person" {
                shape Person
                background #08427b
            }
            element "Software System" {
                background #1168bd
            }
            element "External" {
                background #999999
            }
            element "Container" {
                background #438dd5
                width 400
            }
            element "Component" {
                background #85bbf0
                color #000000
                width 400
            }
            element "Library" {
                background #5a9bd8
            }
            element "Store" {
                shape Cylinder
            }
            element "Planned" {
                border dashed
                background #e6e6e6
                color #555555
            }
            element "Infrastructure Node" {
                background #ffffff
                color #000000
            }
            element "Deployment Node" {
                color #000000
            }
            relationship "Relationship" {
                style solid
                thickness 2
            }
            relationship "Planned" {
                style dashed
                color #999999
            }
        }
    }
}
