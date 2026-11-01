# Sharadar Fund Prices 可执行操作

## 函数参数

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
| `**filters` | 列过滤条件，原样传给 API，见[列过滤条件](#列过滤条件) |

## 列过滤条件

### 写法

| 类型 | 写法 | 对应 Web API |
|---|---|---|
| 单值 | `ticker="AADR"` | `ticker=AADR` |
| 多值 | `ticker=["AADR", "BAB"]` | `ticker=AADR,BAB` |
| 区间 | `date={"gte": "2017-01-01", "lte": "2017-10-30"}` | `date.gte=2017-01-01&date.lte=2017-10-30` |

区间的键可用 `gt`、`gte`、`lt`、`lte`，日期格式为 `YYYY-MM-DD`。多个过滤条件之间是"且"的关系。

### SFP 可过滤列

来自 `INDICATORS` 表（`isfilter = Y`）。只有这几列能出现在 `**filters` 中，其余列只能通过 `columns` 选取。

| 列 | 可过滤 | 主键 |
|---|---|---|
| `ticker` | ✅ | ✅ |
| `date` | ✅ | ✅ |
| `lastupdated` | ✅ | |
| `open, high, low, close, volume, closeadj, closeunadj` | | |

其他表的可过滤列用 `download_table("INDICATORS", path, method="get", table="<表代码>")` 查询，看 `isfilter` 列。

## 操作对照

| # | 操作 | 官方 Python 写法 | `download_table` 写法 | 实测行数 |
|---|---|---|---|---|
| 2 | 单个 ticker | `get_table('SHARADAR/SFP', ticker='AADR')` | `download_table("SFP", path, ticker="AADR")` | 4,096 |
| 3 | 多个 ticker | `get_table('SHARADAR/SFP', ticker=['AADR','BAB'])` | `download_table("SFP", path, ticker=["AADR", "BAB"])` | 8,360 |
| 4 | 单日 | `get_table('SHARADAR/SFP', date='2017-10-30')` | `download_table("SFP", path, date="2017-10-30")` | 2,805 |
| 5 | 日期区间 | `get_table('SHARADAR/SFP', date={'gte':'2017-01-01','lte':'2017-10-30'}, ticker='AADR')` | `download_table("SFP", path, date={"gte": "2017-01-01", "lte": "2017-10-30"}, ticker="AADR")` | 209 |
| 6 | 指定列 | `get_table('SHARADAR/SFP', qopts={'columns': [...]}, ticker='AADR')` | `download_table("SFP", path, columns=["ticker", "date", "open", "high", "low", "close", "volume", "closeadj"], ticker="AADR")` | 4,096（8 列） |
| 7 | 增量更新 | `get_table('SHARADAR/SFP', lastupdated={'gte':'2017-11-03'}, ticker='AADR')` | `download_table("SFP", path, lastupdated={"gte": "2017-11-03"}, ticker="AADR")` | 视日期而定 |
| 8 | 超过 1 万行 | `get_table(..., paginate=True)` 或 `qopts.export=true` | 默认的 `method="export"` 即可，例如 `download_table("SFP", path)` 下载整表 | 无上限 |
| 8 | 限制行数 | — | `download_table("SFP", path, method="get", limit=500, date={"gte": "2017-10-01"})` | 500 |
| 9 | Ticker 元数据 | `get_table('SHARADAR/TICKERS', table='SFP', ticker='AADR')` | `download_table("TICKERS", path, table="SFP", ticker="AADR")` | 1（28 列） |
| 10 | 某表的字段说明 | `get_table('SHARADAR/INDICATORS', table='SFP')` | `download_table("INDICATORS", path, table="SFP")` | 10 |
| 11 | 某字段的说明 | `get_table('SHARADAR/INDICATORS', indicator='close')` | `download_table("INDICATORS", path, indicator="close")` | 2 |
| 12 | 公司行为：按 ticker | `get_table('SHARADAR/ACTIONS', ticker='AADR')` | `download_table("ACTIONS", path, ticker="AADR")` | 51 |
| 13 | 公司行为：按日期 | `get_table('SHARADAR/ACTIONS', date='2018-10-29')` | `download_table("ACTIONS", path, date={"gte": "2018-10-29"})` | 视日期而定 |
| 14 | 公司行为：按类型 | `get_table('SHARADAR/ACTIONS', action='split')` | `download_table("ACTIONS", path, action="split")` | — |
| 15 | 指标：按 ticker | `get_table('SHARADAR/METRICS', ticker='AADR')` | `download_table("METRICS", path, ticker="AADR")` | 1（22 列） |

第 9、10 项的 `table="SFP"` 是 `TICKERS` / `INDICATORS` 表里的一列，不是函数的 `table` 参数。函数的 `table` 和 `path` 只能按位置传，所以两者不会冲突。

## 不支持的操作

| # | 操作 | 原因 | 替代方式 |
|---|---|---|---|
| 16 | 表配置元数据 `.../SFP/metadata.json` | 这是 Web API 专用接口，不是数据表 | 第 10 项 `INDICATORS` 已经给出列名、是否可过滤、是否主键 |
| 17 | JSON / XML 格式 | 只是 Web API 的输出格式，Python 端没有意义 | 统一输出 CSV（zip） |
