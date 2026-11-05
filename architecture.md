# Architecture

本文件描述 research_spec.md 中各章节的代码文件，以及 M0 工程基础。方法看 research_spec.md，实现细节看各文件的 docstring。后续操作中的有任何改动，顺序应先改本文件，再写对应代码。

## 约定

- 存储：面板数据为长表，一行一个 (instrument_id, timestamp)；所有表都存 parquet。
- 截面 / 时序：截面代码放 `src/fbs/eval/cs/`、`src/fbs/model/cs/`，时序代码放 `src/fbs/eval/ts/`、`src/fbs/model/ts/`，两者互不 import

## M0 — 工程基础（Makefile、src/fbs/api/）

项目的工程基础：开发命令和后端 API，不包含研究方法，所以 research_spec.md 中没有对应章节（research_spec.md 的 M0 是研究框架，不含代码）。后端 API 是 M1 之上的一层薄封装，只调用 `fbs.etl`。

### 开发命令（仓库根目录）

| 文件 | 章节 | 用途 | 描述 |
| --- | --- | --- | --- |
| `Makefile` | M0 | 常用命令 | 虚拟环境、安装、`.env`、启动后端、清理数据，`make help` 列出全部 |
| `pyproject.toml` | M0 | 依赖 | fbs 包及其依赖，研究代码和后端共用 |

### 后端 API（src/fbs/api/）

routers、schemas 按资源一一对应，routers 只处理 HTTP，业务逻辑放在 services。

| 文件 | 章节 | 用途 | 描述 |
| --- | --- | --- | --- |
| `main.py` | M0 | 应用入口 | 创建 FastAPI 应用，所有路由挂在 `/api` 下 |
| `routers/tables.py` | M0 | 表结构接口 | `GET /api/tables` 各产品的表；`GET /api/tables/{table}/schema` 列、可过滤列、主键 |
| `routers/downloads.py` | M0 | 下载接口 | `POST /api/downloads` 发起下载；`GET /api/downloads` 全部任务；`GET /api/downloads/{job_id}` 任务状态 |
| `routers/files.py` | M0 | 文件接口 | `GET /api/files` bronze 层已下载的文件 |
| `schemas/` | M0 | 请求与响应 | Pydantic 模型；`tables.py` 定义 5 个产品及其表，`downloads.py` 校验产品、表、列和过滤条件 |
| `services/jobs.py` | M0、M1.1.3 | 下载任务 | 内存中的任务登记；同一文件正在下载或当天已下载时不重复下载；后台调用 `download_table` |
| `services/catalog.py` | M0 | 表结构 | 从最新的 INDICATORS 下载读取各表的列、可过滤列、主键；没有时先自动下载 |

## M1 — 数据ETL（src/fbs/etl/）

### M1.1 — 数据提取（src/fbs/etl/extract/）

| 文件 | 章节 | 用途 | 描述 |
| --- | --- | --- | --- |
| `sharadar.py` | M1.1、M1.1.3 | 数据提取 | Sharadar 数据下载，数据文件旁写同名 `.json` 记录完整的下载参数 |

### M1.2 — 数据变换（src/fbs/etl/transform/）

| 文件 | 章节 | 用途 | 描述 |
| --- | --- | --- | --- |
| `unify.py` | M1.2.1 | 格式统一 | 时间（UTC）、列名（field_map.csv）、各资产类别默认口径 |
| `identifiers.py` | M1.2.2 | 标识符 | 数据源信息、映射表（instrument_map.csv）、OpenFIGI 查询、instrument_id |

### M1.3 — 数据存储（src/fbs/etl/storage/）

| 文件 | 章节 | 用途 | 描述 |
| --- | --- | --- | --- |
| `paths.py` | M1、M1.1.3、M1.3.1 | 存储结构 | bronze / silver / gold 目录、原始数据文件命名（产品、表、过滤条件、列、行数上限、下载日期）、清洗数据分类目录 |
| `loading.py` | M1.3.2 | 清洗数据格式 | 写清洗数据文件 |

### 流程（src/fbs/etl/）

| 文件 | 章节 | 用途 | 描述 |
| --- | --- | --- | --- |
| `pipeline.py` | M1 | 流程 | 串起提取、变换、存储 |

### 数据目录（data/）

`{分类}` = `{asset}/{category}/{frequency}`，取值见 research_spec.md M1.3.1。`bronze/`、`silver/`、`gold/` 只保存在本地，仅 `bronze/sample/` 提交到 GitHub。

| 文件 | 章节 | 用途 | 描述 |
| --- | --- | --- | --- |
| `data_library.md` | M1.1.2 | 数据源卡片 | 每个数据源一张卡片 |
| `dictionary/` | M1.2.1、M1.2.2 | 映射表 | field_map.csv、instrument_map.csv |
| `bronze/{source}_{product}/{table}/` | M1.1.3 | 原始数据 | 数据提取的结果，原样保存，文件名为下载日期和过滤条件，旁有同名 `.json` |
| `bronze/sample/{source}_{product}/` | M1.1.3 | 样本数据 | 每个产品每张表的小样本和 README（主键、可过滤列、下载方法） |
| `silver/` | M1.2 | 中间数据 | 数据变换过程中的中间结果 |
| `gold/{分类}/` | M1.3.1、M1.3.2 | 清洗数据 | 数据变换的结果，研究直接读取，可选择上传到 S3 |

## M3 — 因子研究与评价（src/fbs/eval/）

### M3.2 — 截面（src/fbs/eval/cs/）

| 文件 | 章节 | 用途 | 描述 |
| --- | --- | --- | --- |
| `factors.py` | M3.2.2 | 因子预处理 | 因子描述统计、异常值修正、空缺值处理、分布调整、因子中性化 |
| `rebalance.py` | M3.2.3 | 调仓频率 | 调仓日 |
| `returns.py` | M3.2.4 | 未来收益率 | 未来收益率、波动率调整 |
| `segment.py` | M3.2.5 | 样本内分组 | 全样本；分组：按期分组、按市值分组、按行业分组 |
| `metrics.py` | M3.2.6 | 因子评价指标 | 主指标：Rank IC、分层价差、Fama-MacBeth 回归；方向判断：反向检验、U 形检验；副指标：IC 衰减、分层 CVaR、分层换手率、分层净值、分层夏普率、分层最大回撤、因子风险画像 |
| `score.py` | M3.2.7 | 因子综合评分 | 显著性、属性计算、属性合成、综合评分 |
| `selection.py` | M3.2.8 | 因子选择 | 因子排名、因子互补性、因子交易表现 |
| `pipeline.py` | M3.2 | 流程 | 串起 M3.2.1–M3.2.8 因子截面研究流程 |

### M3.3 — 时序（src/fbs/eval/ts/）

## M4 — 因子组合（src/fbs/model/）

### M4.2 — 截面（src/fbs/model/cs/）

| 文件 | 章节 | 用途 | 描述 |
| --- | --- | --- | --- |
| `standardize.py` | M4.2.1 | 因子值标准化 | Gauss-rank、z-score |
| `label.py` | M4.2.2 | 未来收益率调整 | 均值调整、波动率调整、Gauss-rank、z-score |
| `models.py` | M4.2.3 | 模型选择 | 等权加法、Ridge Regression、XGBoost、Transformer |
| `missing.py` | M4.2.4 | 数据处理 | 各模型的缺失值处理 |
| `train_model.py` | M4.2.5 | 模型训练 | 训练目标、训练轮数、选择超参数与模型 |
| `eval_model.py` | M4.2.6 | 模型检验 | 在 OOS Test 上评价一次，与等权加法对比 |
| `pipeline.py` | M4.2 | 流程 | 串起 M4.2.1–M4.2.6 截面因子组合流程 |

### M4.3 — 时序（src/fbs/model/ts/）
