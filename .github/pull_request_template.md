<!--
PR 标题格式：<JIRA 编号> <一句话说明改动>
例如：OXQ-50 完善因子策略研究、回测与 Alpaca 实盘交易系统

填写说明：
- 用中文写，代码、路径、命令用反引号包起来。
- “主要改动”下只保留本 PR 涉及的模块，没改动的模块整节删掉。
- 这类灰色注释是给你看的提示，不会显示在 PR 页面上，可以保留也可以删掉。
-->

## 摘要

<!-- 2–4 句话：这个 PR 解决什么问题，把项目从什么状态带到什么状态。 -->

本 PR ……

关联任务：<!-- 例如 OXQ-50 / #12 -->

主要改动包括：

<!-- 用 3–6 条概括最重要的改动，细节写在下面的“主要改动”里。 -->
- 
- 
- 

## 主要改动

### 依赖与环境
<!-- pyproject.toml / uv.lock / Python 版本 / 可选依赖 / Makefile 命令 -->
- 

### 架构与文档
<!-- C4 图（docs/architecture/）、模块 README、根目录 README -->
- 

### 回测模块
<!-- src/fbs/backtesting：收益计算、调仓频率、绩效指标、样本划分 -->
- 

### 实盘交易模块
<!-- src/fbs/live：策略加载、rebalance / status / performance / halt / flatten、报告 -->
- 

### 风控与订单执行
<!-- src/fbs/risk（pre-trade / post-trade）、src/fbs/execution -->
- 

### 策略体系
<!-- strategy/ 目录、strategy_template、具体策略的 config.yaml / data.py / weights.py -->
- 

### 研究模块
<!-- src/fbs/research、src/fbs/research/eval -->
- 

### 数据与安全
<!-- src/fbs/etl、Bronze → Gold 数据流程、.gitignore、.env / 密钥处理 -->
- 

### 其他
<!-- 不属于上面任何一类的改动 -->
- 

## 移除内容

<!-- 删除或迁移的文件、接口、依赖。迁移的写清楚新位置。没有就写“无”。 -->
- 

## 需要 Reviewer 重点关注

<!-- 可选：有风险的地方、没把握的设计、需要讨论的取舍。没有就删掉这一节。 -->
