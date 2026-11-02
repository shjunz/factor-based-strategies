# Sharadar Fund Prices 样本数据

| 表 | 主键 | 取样方式 | 频率 |
|---|---|---|---|
| `SFP.csv` | `ticker, date` | SPY、QQQ 在 2024-01-02 至 2024-01-05 的 4 个交易日 | daily |
| `METRICS.csv` | `ticker, date` | SPY，另 2 个在市 ticker、2 个已退市 ticker | snapshot |
| `ACTIONS.csv` | `date, action, ticker, name, contraticker, contraname` | 2024 年一季度出现的每种 `action` 各一行 | event |
| `TICKERS.csv` | `table, permaticker, ticker` | 每种 `table` 各一行 | snapshot |
| `INDICATORS.csv` | `table, indicator` | 每种 `table` 各一行 | snapshot |

## 主键取值

- **SFP**：每个 `ticker` 每个交易日一行。2024 年 1 月 SPY 共 21 行，正好是当月全部交易日，无重复主键。
- **METRICS**：每个 `ticker` 只有一行，`date` 是该 ticker 最后一个交易日（在市的为最新交易日 2026-10-30，已退市的如 MEDRF 为 1998-12-08），`lastupdated` 全部是 2026-10-31。整表每天整体刷新，不保留历史。
- **ACTIONS**：`action` 在 2024 年一季度出现 29 种：acquisitionby、acquisitioncash、acquisitioncashusd、acquisitionof、acquisitionstock、adrratiosplit、bankruptcyliquidation、delisted、dividend、exchangefrom、exchangeto、listed、mergerfrom、mergerto、namechangefrom、namechangeto、regulatorydelisting、relation、sicchangefrom、sicchangeto、spacmerger、spacunitseparation、spinoff、spinoffdividend、split、spunofffrom、tickerchangefrom、tickerchangeto、voluntarydelisting。完整的 75 种见 INDICATORS 的 `ACTIONTYPES`。只在事件发生的日期有记录。
- **TICKERS**：`table` 有 5 种：SEP、SF1、SF2、SF3B、SFP（SF3、SF3A 没有记录）。同一 `table` 内 `ticker` 不重复。
- **INDICATORS**：`table` 有 17 种：ACTIONS、ACTIONTYPES、DAILY、EVENTCODES、EVENTS、INDICATORS、METRICS、SEP、SF1、SF2、SF3、SF3A、SF3B、SFP、SP500、TABLE-DESCRIPTIONS、TICKERS。

## 可过滤列

来自 `INDICATORS` 表（`isfilter = Y`、`isprimarykey = Y`）。只有可过滤列能出现在 `**filters` 中，其余列只能通过 `columns` 选取。完整列名见同目录 CSV 的表头。

### SFP

| 列 | 可过滤 | 主键 |
|---|---|---|
| `ticker` | ✅ | ✅ |
| `date` | ✅ | ✅ |
| `lastupdated` | ✅ | |
| `open, high, low, close, volume, closeadj, closeunadj` | | |

### METRICS

| 列 | 可过滤 | 主键 |
|---|---|---|
| `ticker` | ✅ | ✅ |
| `date` | ✅ | ✅ |
| `lastupdated` | ✅ | |
| beta1y, beta5y, dividendyieldforward, dividendyieldtrailing, high52w, high5y, low52w, low5y 等其余 19 列 | | |

### ACTIONS

| 列 | 可过滤 | 主键 |
|---|---|---|
| `date` | ✅ | ✅ |
| `action` | ✅ | ✅ |
| `ticker` | ✅ | ✅ |
| `name` | | ✅ |
| `contraticker` | ✅ | ✅ |
| `contraname` | | ✅ |
| `value` | | |

### TICKERS

| 列 | 可过滤 | 主键 |
|---|---|---|
| `table` | ✅ | ✅ |
| `permaticker` | ✅ | ✅ |
| `ticker` | ✅ | ✅ |
| `lastupdated` | ✅ | |
| name, exchange, isdelisted, category, cusips, siccode, sicsector, sicindustry 等其余 24 列 | | |

### INDICATORS

| 列 | 可过滤 | 主键 |
|---|---|---|
| `table` | ✅ | ✅ |
| `indicator` | ✅ | ✅ |
| `isfilter, isprimarykey, title, description, unittype` | | |

## 下载方法

### 函数参数

```python
download_table(table, path, method="export", limit=None, columns=None, overwrite=False, **filters)
```

| 参数 | 说明 |
|---|---|
| `table` | 表代码，实际请求 `SHARADAR/{table}` |
| `path` | 输出文件保存地址；两种方式都输出 zip 压缩的 CSV，建议用 `.zip` 后缀 |
| `method` | `"export"`：服务器端批量导出，无行数上限，适合整表或大范围；<br />`"get"`：分页查询，约 100 万行以内，适合小查询 |
| `limit` | 最多返回的行数，仅 `method="get"` 可用。数据未排序，取到的是任意 N 行，不是最早或最新的 N 行 |
| `columns` | 只取这些列（即 `qopts.columns`） |
| `overwrite` | 文件已存在时覆盖，否则报 `FileExistsError` |
| `**filters` | 列过滤条件，原样传给 API，只能用[可过滤列](#可过滤列) |

### 过滤条件写法

| 类型 | 写法 | 对应 Web API |
|---|---|---|
| 单值 | `ticker="AADR"` | `ticker=AADR` |
| 多值 | `ticker=["AADR", "BAB"]` | `ticker=AADR,BAB` |
| 区间 | `date={"gte": "2017-01-01", "lte": "2017-10-30"}` | `date.gte=2017-01-01&date.lte=2017-10-30` |

区间的键可用 `gt`、`gte`、`lt`、`lte`，日期格式为 `YYYY-MM-DD`。多个过滤条件之间是"且"的关系。

### 操作对照

| 操作 | 官方 Python 写法 | `download_table` 写法 | 实测行数 |
|---|---|---|---|
| 单个 ticker | `get_table('SHARADAR/SFP', ticker='AADR')` | `download_table("SFP", path, ticker="AADR")` | 4,096 |
| 多个 ticker | `get_table('SHARADAR/SFP', ticker=['AADR','BAB'])` | `download_table("SFP", path, ticker=["AADR", "BAB"])` | 8,360 |
| 单日 | `get_table('SHARADAR/SFP', date='2017-10-30')` | `download_table("SFP", path, date="2017-10-30")` | 2,805 |
| 日期区间 | `get_table('SHARADAR/SFP', date={'gte':'2017-01-01','lte':'2017-10-30'}, ticker='AADR')` | `download_table("SFP", path, date={"gte": "2017-01-01", "lte": "2017-10-30"}, ticker="AADR")` | 209 |
| 指定列 | `get_table('SHARADAR/SFP', qopts={'columns': [...]}, ticker='AADR')` | `download_table("SFP", path, columns=["ticker", "date", "open", "high", "low", "close", "volume", "closeadj"], ticker="AADR")` | 4,096（8 列） |
| 增量更新 | `get_table('SHARADAR/SFP', lastupdated={'gte':'2017-11-03'}, ticker='AADR')` | `download_table("SFP", path, lastupdated={"gte": "2017-11-03"}, ticker="AADR")` | 视日期而定 |
| 超过 1 万行 | `get_table(..., paginate=True)` 或 `qopts.export=true` | 默认的 `method="export"` 即可，例如 `download_table("SFP", path)` 下载整表 | 无上限 |
| 限制行数 | — | `download_table("SFP", path, method="get", limit=500, date={"gte": "2017-10-01"})` | 500 |
| Ticker 元数据 | `get_table('SHARADAR/TICKERS', table='SFP', ticker='AADR')` | `download_table("TICKERS", path, table="SFP", ticker="AADR")` | 1（28 列） |
| 某表的字段说明 | `get_table('SHARADAR/INDICATORS', table='SFP')` | `download_table("INDICATORS", path, table="SFP")` | 10 |
| 某字段的说明 | `get_table('SHARADAR/INDICATORS', indicator='close')` | `download_table("INDICATORS", path, indicator="close")` | 2 |
| 公司行为：按 ticker | `get_table('SHARADAR/ACTIONS', ticker='AADR')` | `download_table("ACTIONS", path, ticker="AADR")` | 51 |
| 公司行为：按日期 | `get_table('SHARADAR/ACTIONS', date='2018-10-29')` | `download_table("ACTIONS", path, date={"gte": "2018-10-29"})` | 视日期而定 |
| 公司行为：按类型 | `get_table('SHARADAR/ACTIONS', action='split')` | `download_table("ACTIONS", path, action="split")` | — |
| 指标：按 ticker | `get_table('SHARADAR/METRICS', ticker='AADR')` | `download_table("METRICS", path, ticker="AADR")` | 1（22 列） |

Ticker 元数据和字段说明两项中的 `table="SFP"` 是 `TICKERS` / `INDICATORS` 表里的一列，不是函数的 `table` 参数。函数的 `table` 和 `path` 只能按位置传，所以两者不会冲突。

### 不支持的操作

| 操作 | 原因 | 替代方式 |
|---|---|---|
| 表配置元数据 `.../SFP/metadata.json` | 这是 Web API 专用接口，不是数据表 | 「某表的字段说明」一项的 `INDICATORS` 已经给出列名、是否可过滤、是否主键 |
| JSON / XML 格式 | 只是 Web API 的输出格式，Python 端没有意义 | 统一输出 CSV（zip） |
