# Architecture

本文件只描述 research_spec.md 中各章节的代码文件。方法看 research_spec.md，实现细节看各文件的 docstring。后续操作中的有任何改动，顺序应先改本文件，再写对应代码。

## 约定

- 存储：面板数据为长表，一行一个 (instrument_id, timestamp)；所有表都存 parquet。
- 截面 / 时序：截面代码放 `eval/cs/`、`model/cs/`，时序代码放 `eval/ts/`、`model/ts/`，两者互不 import

## M1 — 数据ETL（etl/）

### M1.1 — 数据提取（etl/extract/）

| 文件 | 章节 | 用途 | 描述 |
| --- | --- | --- | --- |
| `sharadar.py` | M1.1 | 数据提取 | Sharadar 数据下载 |

### M1.2 — 数据变换（etl/transform/）

| 文件 | 章节 | 用途 | 描述 |
| --- | --- | --- | --- |
| `unify.py` | M1.2.1 | 格式统一 | 时间（UTC）、列名（field_map.csv）、各资产类别默认口径 |
| `identifiers.py` | M1.2.2 | 标识符 | 数据源信息、映射表（instrument_map.csv）、OpenFIGI 查询、instrument_id |

### M1.3 — 数据存储（etl/storage/）

| 文件 | 章节 | 用途 | 描述 |
| --- | --- | --- | --- |
| `paths.py` | M1.3.1 | 存储结构 | 目录结构、各层文件命名 |
| `loading.py` | M1.3.2 | 清洗数据格式 | 写清洗数据文件 |

### 流程（etl/）

| 文件 | 章节 | 用途 | 描述 |
| --- | --- | --- | --- |
| `pipeline.py` | M1 | 流程 | 串起提取、变换、存储 |

### 数据目录（data/）

`{分类}` = `{asset}/{category}/{frequency}`，取值见 research_spec.md M1.3.1。

| 文件 | 章节 | 用途 | 描述 |
| --- | --- | --- | --- |
| `data_library.md` | M1.1.2 | 数据源卡片 | 每个数据源一张卡片 |
| `dictionary/` | M1.2.1、M1.2.2 | 映射表 | field_map.csv、instrument_map.csv |
| `extraction/{分类}/` | M1.1 | 原始数据 | 数据提取的结果，原样保存 |
| `loading/{分类}/` | M1.3.2 | 清洗数据 | 数据变换的结果，研究直接读取 |

## M3 — 因子研究与评价（eval/）

### M3.2 — 截面（eval/cs/）

| 文件 | 章节 | 用途 | 描述 |
| --- | --- | --- | --- |
| `bars.py` | M3.2.1 | 基础频率 | 跨市场对齐、OHLCV 合成 |
| `returns.py` | M3.2.2 | 未来收益率 | 未来收益率、波动率调整 |
| `factors.py` | M3.2.3 | 因子值 | 因子描述统计、异常值修正、空缺值处理、分布调整、因子中性化 |
| `segment.py` | M3.2.4 | 样本内划分 | 全样本；分组：按期分组、按市值分组、按行业分组 |
| `metrics.py` | M3.2.5 | 因子评价指标 | 主指标：Rank IC、分层价差、Fama-MacBeth 回归；方向判断：反向检验、U 形检验；副指标：IC 衰减、分层 CVaR、分层换手率、分层净值、分层夏普率、分层最大回撤、因子风险画像 |
| `pipeline.py` | M3.2 | 流程 | 串起 M3.2.1–M3.2.5 因子截面研究流程 |

### M3.3 — 时序（eval/ts/）

## M4 — 因子组合（model/）

### M4.1 — 截面（model/cs/）

| 文件 | 章节 | 用途 | 描述 |
| --- | --- | --- | --- |
| `score.py` | M4.1.1 | 因子综合评分 | 显著性、属性计算、属性合成、综合评分 |
| `selection.py` | M4.1.2 | 因子选择 | 因子排名、因子互补性、因子交易表现 |
| `standardize.py` | M4.1.3 | 因子值标准化 | Gauss-rank、z-score |
| `label.py` | M4.1.4 | 未来收益率调整 | 均值调整、波动率调整、Gauss-rank、z-score |
| `models.py` | M4.1.5 | 模型选择 | 等权加法、Ridge Regression、XGBoost、Transformer |
| `missing.py` | M4.1.6 | 数据处理 | 各模型的缺失值处理 |
| `train_model.py` | M4.1.7 | 模型训练 | 训练目标、训练轮数、选择超参数与模型 |
| `eval_model.py` | M4.1.8 | 模型检验 | 在 OOS Test 上评价一次，与等权加法对比 |
| `pipeline.py` | M4.1 | 流程 | 串起 M4.1.1–M4.1.8 截面因子组合流程 |

### M4.2 — 时序（model/ts/）
