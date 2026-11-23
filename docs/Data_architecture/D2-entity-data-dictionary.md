# D2 实体数据字典

D1 只画 13 个主要实体；这里给出它们的字段定义，并展开 D1 没有单独画框的文件内部结构：DD 里的 DataDictionary / DictionaryDataset / ProviderField / ProviderCode，sync_state 里的 Coverage，RunRecord 里的 TargetWeight / OrderIntent / Submission，以及计划中的 SilverFile。分三块：P 数据供应商层（共享）、A 策略数据、B 运行记录。实体之间的关系见 [D1-logical-erd.svg](D1-logical-erd.svg)，文件放在 S3 哪里见 [D3-s3-object-layout.svg](D3-s3-object-layout.svg)，JSON 文件的机器可读定义见 [schemas/](schemas/)。

**读法**

- **键**：PK = 主键，FK = 外键（指向哪个实体写在说明里）
- **必填**：✓ = 必须有；空 = 可以没有或为 null
- **类型**：`date` = `YYYY-MM-DD`；`datetime` = ISO 8601 带时区偏移；`timestamp UTC` = Parquet 里的 UTC 时间戳
- **状态**：已有 = 代码已经这样写；计划 = 设计好了，代码还没有

## 目录

| 实体 | 存储 | S3 key | 写入者 | 状态 |
|---|---|---|---|---|
| **P 数据供应商层** | | `providers/{provider}/`（本地 `src/fbs/etl/provider/{provider}/`） | | |
| [Provider 数据供应商](#provider) | YAML | `providers/{provider}/metadata/provider.yaml` | 人工 | 已有（本地 git）；S3 为计划 |
| [DataDictionary 数据字典快照](#datadictionary) | CSV | `providers/{provider}/metadata/DD_{as_of}_ALL.csv` | 人工（供应商导出） | 已有（本地 git）；S3 为计划 |
| [ProviderDataset 数据表](#providerdataset) | DD 里的行 | 同上 | 同上 | 已有 |
| [ProviderField / ProviderCode 字段与代码表](#providerfield) | DD 里的行 | 同上 | 同上 | 已有 |
| [FieldMap 字段映射](#fieldmap) | CSV | `providers/{provider}/metadata/field_map.csv` | 人工 | 已有（本地 git）；S3 为计划 |
| [RawFile 共享原始下载](#rawfile) | zip（CSV） | `providers/{provider}/bronze/{dataset}/{download_date}_{filters}.zip` | 共享下载任务 | 计划（本地小样本见 `Raw_Data_Sample/`） |
| **A 策略数据** | | `strategy/{name}/data/` | | |
| [BronzeFile 原始下载文件](#bronzefile) | zip（CSV） | `**/bronze/{source}_{product}/{dataset}/{download_date}_{filters}.zip` | `fbs.etl.provider.sharadar.extract.download_table` | 已有 |
| [DownloadRecord 下载记录](#downloadrecord) | JSON | 同上，`.json` | 同上 | 已有 |
| [GoldTable 清洗表（通用）](#goldtable) | Parquet | `**/gold/{asset_class}/{category}/{frequency}/{source}_{dataset}_{clean_date}.parquet` | `fbs.etl.loading.save_clean`；策略 `data.py` | 已有 |
| [CleanRecord 清洗记录](#cleanrecord) | JSON | 同上，`.json` | `fbs.etl.loading.save_clean` | 已有（策略 gold 为计划） |
| [InstrumentMap 代码映射](#instrumentmap) | CSV | `strategy/{name}/data/gold/instrument_map.csv` | 策略 `data.py` | 已有 |
| [Strategy 策略配置](#strategy) | YAML | `strategy/{name}/config.yaml` | 人工（git 为准） | 已有 |
| [SyncState / Coverage 同步状态](#syncstate) | JSON | `strategy/{name}/data/sync_state.json` | 策略 `data.py` | 已有 |
| [RunRecord 运行记录](#runrecord) | JSON | `strategy/{name}/records/{exec_session}-rebalance.json` | `fbs.live.runner._write_record` | 已有 |
| [OrderIntent / Submission](#orderintent) | RunRecord 内嵌 | 同上 | 同上 | 已有 |
| [Report 报告](#report) | PDF | `strategy/{name}/records/*.pdf` | `fbs.live.report` | 已有 |
| **B 运行记录与 S3 元数据** | | | | |
| [AuditLog / ObjectEntry 审计日志](#auditlog) | JSON | `strategy/{name}/_meta/audit/{run_id}.json` 或 `providers/{provider}/_meta/audit/{run_id}.json` | ECS 任务上传步骤 | 计划 |
| [S3 对象元数据](#s3-object-metadata) | S3 `x-amz-meta-*` 头 | 每个对象 | ECS 任务上传步骤 | 计划 |

---

# P 数据供应商层

每个数据供应商一份，所有策略共享。**Sharadar 是第一个例子**，之后接别的数据 API 照同样结构加一个 `providers/{provider}/`，下面的实体都不用改。

- 本地：`src/fbs/etl/provider/{provider}/`。`metadata/` 进 git；`Raw_Data_Sample/` 是 bronze 的本地小样本，不 commit（`.gitignore`）
- S3：`providers/{provider}/`（计划）。这是唯一一个 **S3 key ≠ 仓库路径** 的前缀：代码和小样本留在 `src/`，S3 上只放 `metadata/` 和完整的 `bronze/`

<a id="provider"></a>
## Provider 数据供应商

`src/fbs/etl/provider/{provider}/metadata/provider.yaml`，`fbs.etl.provider.{provider}.extract` 下载时读取。一个供应商 = `src/fbs/etl/provider/{provider}/` 一个文件夹（Python 子包），至少有 `extract.py`（下载和读取）和 `metadata/`。

**这里不放任何密钥。** `api_key_env` 只是环境变量的名字；key 的值本地放仓库根目录 `.env`（gitignore），生产放 AWS Secrets Manager，作为同名环境变量注入 ECS 任务。代码只按名字读环境变量，不管值从哪来。

| 字段 | 键 | 类型 | 必填 | 说明 | 示例（Sharadar） |
|---|---|---|---|---|---|
| provider | PK | string | ✓ | 小写，用于目录名和文件名 | `sharadar` |
| vendor | | string | ✓ | 数据从哪个平台来 | Nasdaq Data Link |
| api | | string | ✓ | 接口 | datatables `SHARADAR/{dataset}`，`export_table` 导出 zip |
| api_key_env | | string | ✓ | API key 的**环境变量名**（不是 key）。值：本地 `.env`，生产 Secrets Manager | `NASDAQ_DATA_LINK_API_KEY` |
| extractor | | string | ✓ | 下载代码 | `fbs.etl.provider.sharadar.extract.download_table` |

<a id="datadictionary"></a>
## DataDictionary 数据字典快照

供应商导出的数据字典，原样保存，**新版本另存一份**（文件名里带 `as_of`），旧的保留，方便查字段什么时候变过。

| 字段 | 键 | 类型 | 必填 | 说明 | 示例 |
|---|---|---|---|---|---|
| provider | PK, FK→Provider | string | ✓ | | `sharadar` |
| as_of | PK | date | ✓ | 文件名里写成 `YYYYMMDD` | `20261101` |
| filename | | string | ✓ | 完整路径（= S3 key） | `providers/sharadar/metadata/DD_20261101_ALL.csv` |

Sharadar 的 DD 是一张长表，列为 `table, indicator, isfilter, isprimarykey, title, description, unittype`。`table` 列有三种值：

- 数据表名（SF1、SEP…）：每行一个字段 → [ProviderField](#providerfield)
- `TABLE-DESCRIPTIONS`：每行一张表 → [ProviderDataset](#providerdataset)
- `ACTIONTYPES`、`EVENTCODES`：代码表 → [ProviderCode](#providerfield)

别的供应商的数据字典格式不同时，转成同样四个实体即可。

**DD 和表是多对多**：一张表（例 SEP）出现在每一版 DD 里，一版 DD 也列出很多张表。所以表归属于 Provider，不归属于某一版 DD；ProviderDataset / ProviderField 的内容以**最新一版** DD 为准，旧版 DD 只用来查字段什么时候变过。

**DictionaryDataset 字典收录的表**（DD 和表之间的对照表）：每一版 DD 的 `TABLE-DESCRIPTIONS` 里的一行，记录"哪一版 DD 收录了哪张表"。

| 字段 | 键 | 类型 | 必填 | 说明 | 示例 |
|---|---|---|---|---|---|
| provider | PK, FK→DataDictionary / ProviderDataset | string | ✓ | | `sharadar` |
| as_of | PK, FK→DataDictionary | date | ✓ | 哪一版 DD | `2026-11-01` |
| dataset | PK, FK→ProviderDataset | string | ✓ | 哪张表 | `SEP` |
| title | | string | ✓ | 这一版 DD 里写的表名 | Sharadar Equity Prices Table (SEP) |

<a id="providerdataset"></a>
## ProviderDataset 数据表

一张供应商数据表。取代原来 `data/data_library.md` 里的数据卡片（那里的 asset_class 等分类字段并到这里）。

| 字段 | 键 | 类型 | 必填 | 说明 | 示例 |
|---|---|---|---|---|---|
| provider | PK, FK→Provider | string | ✓ | | `sharadar` |
| dataset | PK | string | ✓ | 供应商表名 | `SEP` |
| title | | string | ✓ | DD `TABLE-DESCRIPTIONS.title` | Sharadar Equity Prices Table (SEP) |
| primary_key | | string[] | ✓ | DD 里 `isprimarykey=Y` 的字段 | `[ticker, date]` |
| date_filter | | string | | 增量下载用的列，必须 `isfilter=Y`；空 = 参考表，每次全量 | `date` |
| asset_class / category / frequency | | string | | 进 gold 时的目录层级 | `EQ` / `spot` / `daily` |

**Sharadar 的 14 张表**（来自 `DD_20261101_ALL.csv`；样本 = `Raw_Data_Sample/` 里 2026-06-21 起 5 个月的下载）

| dataset | 内容 | 字段数 | primary_key | date_filter | 样本行数 | 样本 zip |
|---|---|---:|---|---|---:|---:|
| SEP | 股票日线价格 | 10 | ticker, date | date | 682,771 | 14.3 MB |
| SFP | 基金 / ETF 日线价格 | 10 | ticker, date | date | 676,678 | 14.1 MB |
| DAILY | 每日估值指标（市值、PE 等） | 10 | ticker, date | date | 596,695 | 11.4 MB |
| METRICS | 价格类指标（beta、均线、52 周高低） | 22 | ticker, date | date | 13,128 | 0.6 MB |
| SF1 | 财报基本面 | 112 | ticker, dimension, datekey, reportperiod | lastupdated | 1,173,519 | 246.5 MB |
| SF2 | 内部人交易 | 24 | ticker, filingdate, formtype, ownername, rownum | filingdate | 167,531 | 3.9 MB |
| SF3 | 机构持仓明细（13F） | 6 | ticker, investorid, securitytype, date | date（季末） | 5,047,190 | 37.3 MB |
| SF3A | 机构持仓按股票汇总 | 29 | date, ticker | date（季末） | 28,857 | 0.8 MB |
| SF3B | 机构持仓按机构汇总 | 29 | date, investorid | date（季末） | 17,814 | 0.7 MB |
| ACTIONS | 公司行动（拆股、分红、更名、退市…） | 7 | date, action, ticker, name, contraticker, contraname | date | 22,310 | 0.3 MB |
| EVENTS | 8-K 重大事件 | 3 | date, ticker | date | 42,662 | 0.2 MB |
| SP500 | S&P 500 成分变动 | 7 | date, action, ticker | date | 1,531 | <0.1 MB |
| TICKERS | 证券代码和元数据（参考表） | 28 | table, permaticker, ticker | 无（全量） | 74,680 | 4.9 MB |
| INDICATORS | 各表字段说明（参考表） | 7 | table, indicator | 无（全量） | 430 | <0.1 MB |

从样本看到的注意事项：

- **METRICS 实际上是快照**：每个 ticker 只有最新一行，不能当 5 个月的时间序列用。
- **SF1 按 `lastupdated` 增量**：会带回有更新的旧报告期，不只是最近的季度。
- **SF3 / SF3A / SF3B 的 `date` 是季末日**：5 个月只覆盖 2 个季度；SF3 行数最多。
- **ACTIONS 有未来日期**：已公告、还没生效的公司行动。
- **参考表（TICKERS、INDICATORS）没有日期维度**，每次全量下载，靠 `lastupdated` 判断变化。

<a id="providerfield"></a>
## ProviderField / ProviderCode 字段与代码表

**ProviderField**（DD 里数据表的一行）

| 字段 | 键 | 类型 | 必填 | 说明 | 示例 |
|---|---|---|---|---|---|
| provider / dataset | PK, FK→ProviderDataset | string | ✓ | | `sharadar` / `SEP` |
| source_field | PK | string | ✓ | DD `indicator` | `closeadj` |
| title | | string | ✓ | | Close Price (Adjusted) |
| description | | string | | | |
| unittype | | string | | 单位，例 `currency`、`USD millions`、`date (YYYY-MM-DD)`、`text` | `currency` |
| isfilter | | `Y` \| `N` | ✓ | 下载时能不能按它过滤 | `N` |
| isprimarykey | | `Y` \| `N` | ✓ | 是否主键的一部分 | `N` |

**ProviderCode**（DD 里 `ACTIONTYPES`、`EVENTCODES` 的一行）：某些字段的取值是代码，含义要查这里。

| 字段 | 键 | 类型 | 必填 | 说明 | 示例 |
|---|---|---|---|---|---|
| provider | PK, FK→Provider | string | ✓ | | `sharadar` |
| code_set | PK | string | ✓ | 代码表名 | `ACTIONTYPES`（ACTIONS.action，75 个）、`EVENTCODES`（EVENTS.eventcodes，37 个） |
| code | PK | string | ✓ | DD `indicator` | `acquisitionby`、`11` |
| title | | string | ✓ | | Acquisition By |

<a id="fieldmap"></a>
## FieldMap 字段映射

供应商字段名 → 标准字段名。`fbs.etl.unify.rename_fields` 读取。本地 `src/fbs/etl/provider/{provider}/metadata/field_map.csv`。接新供应商时，只要在它自己的 `field_map.csv` 里把字段映射到同一组标准字段，gold 和引擎都不用改。

| 字段 | 键 | 类型 | 必填 | 说明 | 示例 |
|---|---|---|---|---|---|
| provider | PK, FK→ProviderDataset | string | ✓ | 数据供应商，小写 | `sharadar` |
| dataset | PK, FK→ProviderDataset | string | ✓ | 数据表 | `SEP` |
| source_field | PK | string | ✓ | 供应商字段名 | `closeadj` |
| field | | string | ✓ | 标准字段名，成为 GoldTable 的列 | `close_adj` |

<a id="rawfile"></a>
## RawFile 共享原始下载（计划）

供应商层的原始下载：每张表一个文件夹，所有策略共享，**只增不改**。字段和 [BronzeFile](#bronzefile) 一样，旁边同样放 [DownloadRecord](#downloadrecord)。

| 字段 | 键 | 类型 | 必填 | 说明 | 示例 |
|---|---|---|---|---|---|
| filename | PK | string | ✓ | 完整路径（= S3 key） | `providers/sharadar/bronze/SEP/20261121_date=20260621-.zip` |
| provider / dataset | FK→ProviderDataset | string | ✓ | | `sharadar` / `SEP` |
| download_date | | date | ✓ | 文件名里写成 `YYYYMMDD` | `20261121` |
| filters_token | | string | ✓ | 和 BronzeFile 同一规则；通常只按 `date_filter` 过滤，不按 ticker | `date=20260621-`、`ALL` |

> 本地样本 `src/fbs/etl/provider/sharadar/Raw_Data_Sample/{dataset}/` 是一次性下载的，文件名是 `{dataset}_{date_filter}={起}-{止}.zip`（例 `SEP_date=20260621-20261121.zip`），和上面的规则不完全一样；做共享下载任务时改用 `bronze_path` 的规则。

<a id="bronzefile"></a>
## BronzeFile 原始下载文件

供应商原样返回的文件，**只增不改**：每次下载都是一个新文件，同一天同样的过滤条件才会覆盖。

| 字段 | 键 | 类型 | 必填 | 说明 | 示例 |
|---|---|---|---|---|---|
| filename | PK | string | ✓ | 完整路径（= S3 key = 仓库相对路径） | `strategy/{name}/data/bronze/sharadar_equity_prices/SEP/20260102_lastupdated=20251230-_ticker=AAPL,MSFT.zip` |
| source | FK→Dataset | string | ✓ | 目录名里小写 | `sharadar` |
| product | FK→Product | string | ✓ | | `equity_prices` |
| dataset | FK→Dataset | string | ✓ | | `SEP` |
| download_date | | date | ✓ | 文件名里写成 `YYYYMMDD` | `20260102` |
| filters_token | | string | ✓ | 过滤条件按列名排序，`列=值` 用 `_` 连接；范围写 `起-止`，列表用 `,` 连接；不过滤写 `ALL` | `date=20240101-_ticker=QQQ,SPY` |
| suffix | | string | ✓ | | `.zip` |

<a id="downloadrecord"></a>
## DownloadRecord 下载记录

BronzeFile 和 RawFile 旁边的同名 `.json`，两者共用一个 schema：[download-record.schema.json](schemas/download-record.schema.json)。

| 字段 | 键 | 类型 | 必填 | 说明 | 示例 |
|---|---|---|---|---|---|
| filename | PK, FK→BronzeFile / RawFile | string | ✓ | 隐含：数据文件的 filename，扩展名换成 `.json` | |
| provider | | string | | 计划：供应商，接第二个供应商前补上 | `sharadar` |
| table | | string | ✓ | 供应商表名（= dataset） | `SEP` |
| filters | | object | ✓ | 下载时的过滤条件，原样记录 | `{"ticker": ["AAPL"], "date": {"gte": "2024-01-01"}}` |
| columns | | string[] \| null | ✓ | 选取的列；null = 全部 | `null` |
| downloaded_at | | datetime | ✓ | UTC，精确到秒 | `2026-01-02T03:04:05+00:00` |

<a id="goldtable"></a>
## GoldTable 清洗表（通用）

每张供应商表（ProviderDataset）清洗后成为一个 GoldTable，一个 Parquet 文件；同一张表同时只存在一个文件。现在只有日线价格（[GoldPrices](#pricebar)），以后加别的表（例：SF1 基本面）照同样规则加一个 GoldTable，不用新增实体，只在下面补一张「列」表。

规则（所有 GoldTable 共用）：

- 路径里的 `asset_class / category / frequency` 取自 [ProviderDataset](#providerdataset)，不另外维护
- 数据列 = [FieldMap](#fieldmap) 里该 `(provider, dataset)` 的 `field`（标准字段名）
- 主键 = `(strategy, provider, dataset, instrument_id, timestamp)`，五列都写在 parquet 里（不只在路径里），可以直接和 ProviderDataset、Strategy 等 join；个别表需要多一列（例：SF1 同一天有 ARQ / ART 等多个 `dimension`），在该表的「列」表里标 PK
- `timestamp` 按 frequency 对齐：日线 = 交易日收盘时间（XNYS 16:00 New York 换成 UTC）
- 主键重复时留新行；写新文件后删旧文件

**GoldTable 文件**

| 字段 | 键 | 类型 | 必填 | 说明 | 示例 |
|---|---|---|---|---|---|
| filename | PK | string | ✓ | 完整路径（= S3 key） | `strategy/{name}/data/gold/EQ/spot/daily/sharadar_SEP_20260102.parquet` |
| asset_class / category / frequency | | string | ✓ | 目录层级，取自 ProviderDataset | `EQ` / `spot` / `daily` |
| source / dataset | FK→ProviderDataset | string | ✓ | 文件名里 source 小写 | `sharadar` / `SEP` |
| clean_date | | date | ✓ | 文件名里写成 `YYYYMMDD` | `20260102` |

<a id="pricebar"></a>
**GoldPrices 日线价格的列**（`gold/EQ/spot/daily/sharadar_SEP_*.parquet`，已有；标准字段由 `fbs.etl.unify.STANDARD_FIELDS["EQ"]` 定义）

| 列 | 键 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| strategy | PK, FK→Strategy | string | ✓ | 策略文件夹名（与路径一致） |
| provider | PK, FK→ProviderDataset | string | ✓ | `sharadar`（与文件名一致） |
| dataset | PK, FK→ProviderDataset | string | ✓ | `SEP`（与文件名一致） |
| instrument_id | PK, FK→Instrument | string | ✓ | 标的 ID，见下方「已知差异」 |
| timestamp | PK | timestamp UTC | ✓ | 交易日收盘时间（XNYS 16:00 New York 换成 UTC） |
| open / high / low / close | | float | | 原始价格（Sharadar 已做拆股调整） |
| close_raw | | float | | 未调整收盘价（Sharadar `closeunadj`） |
| close_adj | | float | | 拆股和分红都调整的收盘价（Sharadar `closeadj`） |
| volume | | float | | 成交量 |
| clean_date | | date | ✓ | 写出这个文件的日期（与文件名一致） |

约束：主键唯一，行按 `(timestamp, instrument_id)` 排序。策略 `data.py` 已经写这四列；共享层 `save_clean` 计划跟进（目前只有 `instrument_id, timestamp` 和价格列）。

> **已知差异**：仓库共享层 `fbs.etl.provider.sharadar.pipeline.clean_sep` 用 Sharadar `permaticker` 作 instrument_id；策略 `data.py` 用 composite FIGI（来自 `instrument_map.csv`），并且列顺序是 `timestamp, instrument_id, …`。两边的 gold 文件不能直接合并，统一前跨层使用要先换 ID。

<a id="cleanrecord"></a>
## CleanRecord 清洗记录

GoldTable 文件旁边的同名 `.json`。Schema：[clean-record.schema.json](schemas/clean-record.schema.json)。策略 `data.py` 目前不写它（计划补上）。

| 字段 | 键 | 类型 | 必填 | 说明 | 示例 |
|---|---|---|---|---|---|
| filename | PK, FK→GoldTable | string | ✓ | 隐含：GoldTable 文件的 filename，扩展名换成 `.json` | |
| start | | date | ✓ | 最早一行的日期 | `2018-01-02` |
| end | | date | ✓ | 最晚一行的日期 | `2026-01-02` |
| sources | FK→BronzeFile | string[] | ✓ | 用到的原始文件，相对 `data/` 的路径 | `["bronze/sharadar_equity_prices/SEP/20260102_ALL.zip"]` |

<a id="instrumentmap"></a>
## InstrumentMap 代码映射

| 字段 | 键 | 类型 | 必填 | 说明 | 示例 |
|---|---|---|---|---|---|
| strategy | PK, FK→Strategy | string | ✓ | 策略文件夹名，写在 CSV 里 | `strategy_example` |
| source | PK | string | ✓ | 代码来源 | `sharadar` |
| source_id | PK | string | ✓ | 来源里的代码 | `AAPL` |
| instrument_id | FK→Instrument | string | ✓ | composite FIGI | `BBG000B9XRY4` |

已有的映射不再重新查；新股票从 Sharadar TICKERS 查 FIGI（上市中的优先，其次最新的 lastupdated）。

<a id="strategy"></a>
## Strategy 策略配置

`strategy/{name}/config.yaml`，git 里的版本为准，S3 上只是任务运行时的副本。

| 字段 | 键 | 类型 | 必填 | 说明 | 示例 |
|---|---|---|---|---|---|
| strategy | PK | string | ✓ | 文件夹名 `{name}`；其他实体的 `strategy` 外键都指向这里 | `strategy_example` |
| universe | | string[] | ✓ | 股票池 | `[AAPL, MSFT, …]` |
| rebalance | | `D` \| `W` \| `M` | ✓ | 调仓频率 | `M` |
| lookback_sessions | | int | ✓ | 每次往前取多少个交易日 | `300` |
| backtest_start | | date | | 回测报告的回测起点 | `2018-01-01` |
| split | | object | | `is_end`（date）、`embargo_sessions`（int） | |
| params | | object | | 策略自己的参数，`weights.py` 读 | |
| data.field | | string | ✓ | 传给 `weights.py` 的 GoldPrices 列 | `close_adj` |
| paper | | object | | `enabled`、`mode`、`account`、`capital`、`moc_cutoff_minutes`、`limits` | |

<a id="syncstate"></a>
## SyncState / Coverage 同步状态

`strategy/{name}/data/sync_state.json`。Schema：[sync-state.schema.json](schemas/sync-state.schema.json)。**最后写**：写失败只会让下次多下载一些，不会丢数据。删掉它，下次全量重新下载。

| 字段 | 键 | 类型 | 必填 | 说明 | 示例 |
|---|---|---|---|---|---|
| strategy | PK, FK→Strategy | string | ✓ | 策略文件夹名，写在 JSON 里 | `strategy_example` |
| synced | | date \| null | ✓ | 上次同步日期；null = 从未同步 | `2026-01-02` |
| coverage | | object | ✓ | ticker → 本地数据起始日（每个键值对 = 一条 Coverage） | `{"AAPL": "2018-01-01"}` |

<a id="runrecord"></a>
## RunRecord 运行记录

一次 `python -m fbs.live rebalance {name}` 的结果。Schema：[run-record.schema.json](schemas/run-record.schema.json)。

| 字段 | 键 | 类型 | 必填 | 说明 | 示例 |
|---|---|---|---|---|---|
| strategy | PK, FK→Strategy | string | ✓ | | `strategy_example` |
| exec_session | PK | date | ✓ | 下单（收盘市价）的交易日 | `2026-01-02` |
| mode | | `dry_run` \| `submit` | ✓ | 干跑和提交共用一个文件名，靠它区分；干跑不覆盖已提交的记录 | `dry_run` |
| backtest_report | | string | | 同一次运行的回测报告文件名；回测没通过时没有 | `2026-11-20-backtest_IS-20260901-20260930_OOS-20261008-20261119.pdf` |
| signal_session | | date | ✓ | 算信号用的交易日 | `2025-12-31` |
| run_at | | datetime | ✓ | 运行时间，America/New_York | `2026-01-02T15:00:12-05:00` |
| status | | `dry_run` \| `blocked` \| `submitted` \| `partial` | ✓ | partial = 部分订单被拒 | `dry_run` |
| failures | | string[] | ✓ | 失败原因；非空 = 不下单 | `[]` |
| notes | | string[] | ✓ | 提示，例如缩量、跳过的小单 | `[]` |
| targets | | object | ✓ | symbol → 目标权重（每个键值对 = 一条 TargetWeight） | `{"AAPL": 0.095}` |
| orders | | OrderIntent[] | ✓ | 计划订单 | |
| submitted | | Submission[] | ✓ | 提交结果；dry run 为空 | |
| turnover | | float | | 单边换手 / capital；数据检查失败时没有 | `0.4766` |

<a id="orderintent"></a>
## OrderIntent / Submission

内嵌在 RunRecord 里。

**OrderIntent**

| 字段 | 键 | 类型 | 必填 | 说明 | 示例 |
|---|---|---|---|---|---|
| client_order_id | PK | string | ✓ | `{strategy}-{exec_session}-{symbol}-{reason}`，重跑不变，保证同一订单不会发两次 | `strategy_example-2026-01-02-AAPL-adjust` |
| symbol | | string | ✓ | Alpaca 代码 | `AAPL` |
| side | | `buy` \| `sell` | ✓ | | `buy` |
| qty | | int ≥ 1 | ✓ | 整股 | `27` |
| target_weight | | float | ✓ | | `0.095` |
| reason | | `open` \| `close` \| `adjust` | ✓ | | `adjust` |

**Submission**

| 字段 | 键 | 类型 | 必填 | 说明 | 示例 |
|---|---|---|---|---|---|
| client_order_id | PK, FK→OrderIntent | string | ✓ | | |
| status | | string | ✓ | Alpaca 订单状态、`already_present`，或 `rejected: {原因}` | `accepted` |

<a id="report"></a>
## Report 报告

| 字段 | 键 | 类型 | 必填 | 说明 | 示例 |
|---|---|---|---|---|---|
| filename | PK | string | ✓ | 完整路径（= S3 key） | `strategy/{name}/records/2026-01-02-backtest_IS-20180102-20221230_OOS-20230202-20251231.pdf` |
| kind | | `backtest` \| `live_trading` | ✓ | backtest = 每次运行一份，`{exec_session}-backtest_IS-{起止}_OOS-{起止}.pdf`；live_trading = `{last_session}-live-trading.pdf` | |
| run | FK→RunRecord | | | 只有 run 类型有 | |

<a id="auditlog"></a>
## AuditLog / ObjectEntry 审计日志（计划）

每个 ECS 任务结束时写一份，**成功和失败都写**。Schema：[audit-log.schema.json](schemas/audit-log.schema.json)。作用：知道每个 S3 对象是哪次运行、哪个代码版本写的；用 `version_id` 可以把策略文件夹还原到任意一次运行结束时的状态。

**AuditLog**

| 字段 | 键 | 类型 | 必填 | 说明 | 示例 |
|---|---|---|---|---|---|
| schema | | const | ✓ | `urn:fbs:schema:audit-log:1` | |
| run_id | PK | string | ✓ | 任务开始时间 UTC，`YYYYMMDDTHHMMSSZ` | `20260102T200012Z` |
| strategy | FK→Strategy | string | 二选一 | 策略任务写 | `strategy_example` |
| provider | FK→Provider | string | 二选一 | 共享下载任务写 | `sharadar` |
| command | | string | | 容器命令 | `python -m fbs.live rebalance strategy_example --submit` |
| started_at / finished_at | | datetime | ✓ | | |
| exit_code | | int | ✓ | 0 正常；1 blocked 或部分拒单；其他 = 异常 | `0` |
| git_sha | | string | ✓ | 镜像里的代码版本 | `3eaab8d` |
| image_digest | | string | | | `sha256:…` |
| run_record | FK→RunRecord | string \| null | | 这次写出的运行记录 key | |
| objects | | ObjectEntry[] | ✓ | 新增或改动的对象 | |
| deleted | | string[] | ✓ | 在 S3 上删掉的 key（例如被替换的旧 gold 文件） | |

**ObjectEntry**

| 字段 | 键 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| run_id | PK, FK→AuditLog | string | ✓ | 隐含 |
| key | PK | string | ✓ | S3 key |
| sha256 | | string(64 hex) | ✓ | 文件内容哈希 |
| size | | int | ✓ | 字节 |
| version_id | | string | ✓ | S3 PutObject 返回的 VersionId |
| content_type | | string | | |

<a id="s3-object-metadata"></a>
## S3 对象元数据（计划）

每个对象上传时附带的用户元数据头。Schema：[s3-object-metadata.schema.json](schemas/s3-object-metadata.schema.json)。S3 限制用户元数据总共 ≤ 2 KB，所以这里只放定位和校验字段，详细内容在同名 `.json` 和 AuditLog 里。

| 头 | 必填 | 说明 | 示例 |
|---|---|---|---|
| `x-amz-meta-sha256` | ✓ | 文件内容 SHA-256 | `9f86d0…` |
| `x-amz-meta-producer` | ✓ | 写出文件的模块 | `fbs.etl.provider.sharadar.extract` |
| `x-amz-meta-run-id` | ✓ | 对应 AuditLog.run_id | `20260102T200012Z` |
| `x-amz-meta-git-sha` | ✓ | | `3eaab8d` |
| `x-amz-meta-schema` | | JSON 文件对应的 schema `$id` | `urn:fbs:schema:run-record:1` |
| `x-amz-meta-layer` | | `bronze` \| `gold` \| `state` \| `records` \| `meta` \| `config` \| `metadata`（供应商层的 DD、field_map） | `bronze` |
| `x-amz-meta-sidecar` | | 同名 `.json` 元数据的 key | |
