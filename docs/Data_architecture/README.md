# Data Architecture 数据架构

C4 图（`docs/C4_Architecture/L*.svg`）讲**程序**怎么分；这里的 5 张图讲**数据**：有哪些、长什么样、存在哪、怎么产生和保留。

**统一存储：Amazon S3。** 一个桶 `s3://{FBS_S3_BUCKET}/`，两个顶层前缀：

- `strategy/{name}/`：每个策略一份。**S3 key = 文件在仓库里的相对路径**，本地和 S3 一一对应，同步不需要改名。
- `providers/{provider}/`（计划）：**数据供应商层**，所有策略共享，存供应商的数据字典、字段映射和完整的原始下载。本地镜像是 `src/fbs/etl/provider/{provider}/`。这是唯一一个 key ≠ 仓库路径的前缀：代码留在 `src/`，S3 上只有数据。

## 数据供应商层（Sharadar 是例子）

之后会接不同数据供应商的 API，所以供应商相关的东西都按同一结构放，**Sharadar 是第一个例子**：

| 放什么 | 本地 | S3（计划） | 进 git |
|---|---|---|---|
| 数据字典快照 DataDictionary | `src/fbs/etl/provider/sharadar/metadata/DD_20261101_ALL.csv` | `providers/sharadar/metadata/DD_{as_of}_ALL.csv` | 是 |
| 字段映射 FieldMap | `src/fbs/etl/provider/sharadar/metadata/field_map.csv` | `providers/sharadar/metadata/field_map.csv` | 是 |
| 供应商信息 Provider（只有 key 的变量名） | `src/fbs/etl/provider/sharadar/metadata/provider.yaml` | `providers/sharadar/metadata/provider.yaml` | 是 |
| API key 的值 | 本地 `.env`；生产 AWS Secrets Manager | **不上 S3** | **否** |
| 原始下载 RawFile，每张表一个文件夹 | `src/fbs/etl/provider/sharadar/Raw_Data_Sample/{dataset}/`（5 个月小样本，测试用） | `providers/sharadar/bronze/{dataset}/`（完整，只增不改） | **否** |
| 下载代码 | `src/fbs/etl/provider/sharadar/extract.py` | — | 是 |

为什么原始数据也要上 S3：

1. **多个策略共享**：现在每个策略自己调 API 下载自己 universe 的 bronze，同样的行会下好几遍。共享层每张表只下一次，策略从里面取子集。
2. **原始记录要能找回**：供应商会改历史（Sharadar 拆股、分红会改价格），bronze 只增不改，配合 S3 版本控制就能复现任何一天的数据。
3. **API key 会过期 / 有调用限制**：S3 上有完整副本，不依赖某一个 key 随时可用。

接一个新供应商要做的事：

1. 新建 `src/fbs/etl/provider/{provider}/`，写 `extract.py`（`download_table`、`read_table`，下载时写 DownloadRecord）
2. 把供应商的数据字典存成 `metadata/DD_{as_of}_ALL.csv`，转成 ProviderDataset / ProviderField / ProviderCode（D2）
3. 写 `metadata/field_map.csv`，把字段映射到标准字段（GoldTable 的列）
4. 写 `metadata/provider.yaml`：provider、vendor、api、**api_key_env（只写环境变量的名字，不写 key）**、extractor
5. 放 API key 的值，**不进 git**：
   - 本地：仓库根目录 `.env` 里加一行 `{api_key_env}=...`
   - 生产：在 AWS Secrets Manager 建一个 secret，加到 ECS 任务定义的 `secrets` 里，作为同名环境变量注入（和 `NASDAQ_DATA_LINK_API_KEY`、`ALPACA_*` 一样，见 [L2-deployment-alpaca](../C4_Architecture/L2-deployment-alpaca.svg)、[L2-deployment-ibkr](../C4_Architecture/L2-deployment-ibkr.svg)）

gold 的格式和引擎都不用改。Sharadar 14 张表的主键、增量过滤列和样本大小见 [D2 ProviderDataset](D2-entity-data-dictionary.md#providerdataset)。

| # | 图 | 回答什么 | 文件 |
|---|---|---|---|
| D1 | Logical ERD 逻辑实体关系图（crow's foot） | 有哪些数据实体，主键和关系 | [D1-logical-erd.svg](D1-logical-erd.svg) · [源](D1-logical-erd.puml) |
| D2 | Entity Data Dictionary 实体数据字典 | 每个实体的字段、类型、必填、示例 | [D2-entity-data-dictionary.md](D2-entity-data-dictionary.md) |
| D3 | S3 Object Layout S3 对象布局 | 每类文件放在哪个 key | [D3-s3-object-layout.svg](D3-s3-object-layout.svg) · [源](D3-s3-object-layout.puml) |
| D4 | JSON Schema | 每类元数据 JSON 的结构（机器可校验） | [D4-json-schema.svg](D4-json-schema.svg) · [源](D4-json-schema.puml) · [schemas/](schemas/) |
| D5 | Data Lifecycle Diagram 数据生命周期 | 一次定时任务里数据怎么产生、上传；S3 里保留多久 | [D5-data-lifecycle.svg](D5-data-lifecycle.svg) · [源](D5-data-lifecycle.puml) |

建议阅读顺序：D1 → D2 → D3 → D4 → D5。D5 里的 ⑧-㉕ 和 [L2-deployment-alpaca.svg](../C4_Architecture/L2-deployment-alpaca.svg)、[L2-deployment-ibkr.svg](../C4_Architecture/L2-deployment-ibkr.svg) 的编号一致。

## 元数据怎么记

三层，从细到粗：

1. **同名 `.json`**（已有）：每个数据文件旁边一份，说明它从哪来。bronze 写 DownloadRecord，gold 写 CleanRecord；`sync_state.json` 和 `records/*.json` 本身就是元数据。
2. **S3 对象元数据头 `x-amz-meta-*`**（计划）：每个对象上传时带 sha256、producer、run-id、git-sha，不用下载就能知道它是谁、哪次运行写的。
3. **审计日志 `_meta/audit/{run_id}.json`**（计划）：每个 ECS 任务结束时写一份，列出这次上传的每个对象和它的 S3 `version_id`，可以把策略文件夹还原到任意一次运行结束时的状态。

字段定义见 [D2](D2-entity-data-dictionary.md)，结构见 [schemas/](schemas/)。

## 现状与计划

图里灰色 = 计划中（代码里还没有）：

| 项目 | 现状 |
|---|---|
| 供应商 metadata（DD、field_map） | 已有：`src/fbs/etl/provider/sharadar/metadata/`（git）；S3 `providers/` 为计划 |
| 供应商共享原始下载 | **没有**：只有本地小样本 `Raw_Data_Sample/`（不 commit）；共享下载任务和 S3 `providers/{provider}/bronze/` 为计划 |
| DownloadRecord 的 `provider` 字段 | **没有**：接第二个供应商前补上（schema 里已是可选字段） |
| bronze / gold 的同名 `.json` | 已有：`fbs.etl.provider.sharadar.extract`、`fbs.etl.loading` |
| 策略 gold 的 CleanRecord | **没有**：策略 `data.py` 写 gold 时不写 `.json` |
| S3 上传 / 下载 | **没有**：`src/` 里还没有 S3 代码；L2-deployment-alpaca / -ibkr 里 ECS 任务开始下载、结束上传是设计 |
| `x-amz-meta-*` 头、`_meta/audit/` | **没有** |
| S3 生命周期规则（D5 图例） | **建议**，还没配置到桶上 |

**已知差异**：仓库共享层 gold 用 Sharadar `permaticker` 作 `instrument_id`，策略 gold 用 composite FIGI，两边不能直接合并（见 [D2 GoldTable](D2-entity-data-dictionary.md#goldtable-清洗表通用)）。

## 修改和重新生成

- 改图：编辑 `*.puml`，然后在仓库根目录运行 `make data-diagrams` 生成 SVG（用和 C4 图同一个 PlantUML jar，没有就先 `make diagram-tools`）。
- 改字段：先改 `schemas/*.schema.json`，再同步 D2 和 D4。
- 校验已有文件是否符合 schema：

  ```bash
  uv run --no-project --with jsonschema python -c "
  import json, glob
  from jsonschema import Draft202012Validator as V, FormatChecker
  S = 'docs/Data_architecture/schemas/'
  for name, pat in [('download-record', '**/bronze/**/*.json'),
                    ('sync-state', 'strategy/*/data/sync_state.json'),
                    ('run-record', 'strategy/*/records/*.json')]:
      v = V(json.load(open(S + name + '.schema.json')), format_checker=FormatChecker())
      for f in glob.glob(pat, recursive=True):
          for e in v.iter_errors(json.load(open(f))): print(f, e.message)
  "
  ```
