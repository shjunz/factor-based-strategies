# Sharadar Equity Prices 样本数据

| 表 | 主键 | 取样方式 | 频率 |
|---|---|---|---|
| `SEP.csv` | `ticker, date` | AAPL、MSFT 在 2024-01-02 至 2024-01-05 的 4 个交易日 | daily |
| `METRICS.csv` | `ticker, date` | 与 Sharadar Fund Prices 共用同一张表，样本相同 | snapshot |
| `ACTIONS.csv` | `date, action, ticker, name, contraticker, contraname` | 与 Sharadar Fund Prices 共用同一张表，样本相同 | event |
| `TICKERS.csv` | `table, permaticker, ticker` | 与 Sharadar Fund Prices 共用同一张表，样本相同 | snapshot |
| `INDICATORS.csv` | `table, indicator` | 与 Sharadar Fund Prices 共用同一张表，样本相同 | snapshot |

## 主键取值

- **SEP**：每个 `ticker` 每个交易日一行，列与 SFP 完全相同。2024 年 1 月 AAPL 共 21 行，正好是当月全部交易日，无重复主键。
- **METRICS、ACTIONS、TICKERS、INDICATORS**：与 Sharadar Fund Prices 是同一张表，代码相同，只需下载一次。主键取值见 [sharadar_fund_prices/README.md](../sharadar_fund_prices/README.md#主键取值)。TICKERS 中本产品对应 `table = SEP` 的行。

## 可过滤列

来自 `INDICATORS` 表（`isfilter = Y`、`isprimarykey = Y`）。只有可过滤列能出现在 `**filters` 中，其余列只能通过 `columns` 选取。完整列名见同目录 CSV 的表头。

### SEP

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
| 单值 | `ticker="AAPL"` | `ticker=AAPL` |
| 多值 | `ticker=["AAPL", "MSFT"]` | `ticker=AAPL,MSFT` |
| 区间 | `date={"gte": "2024-01-01", "lte": "2024-01-31"}` | `date.gte=2024-01-01&date.lte=2024-01-31` |

区间的键可用 `gt`、`gte`、`lt`、`lte`，日期格式为 `YYYY-MM-DD`。多个过滤条件之间是"且"的关系。

### 操作对照

| 操作 | 官方 Python 写法 | `download_table` 写法 | 实测行数 |
|---|---|---|---|
| 单个 ticker、日期区间 | `get_table('SHARADAR/SEP', ticker='AAPL', date={'gte':'2024-01-01','lte':'2024-01-31'})` | `download_table("SEP", path, ticker="AAPL", date={"gte": "2024-01-01", "lte": "2024-01-31"})` | 21 |
| 多个 ticker、日期区间 | `get_table('SHARADAR/SEP', ticker=['AAPL','MSFT'], date={'gte':'2024-01-02','lte':'2024-01-05'})` | `download_table("SEP", path, ticker=["AAPL", "MSFT"], date={"gte": "2024-01-02", "lte": "2024-01-05"})` | 8 |
| 超过 1 万行 | `get_table(..., paginate=True)` 或 `qopts.export=true` | 默认的 `method="export"` 即可，例如 `download_table("SEP", path)` 下载整表 | 无上限 |
| Ticker 元数据 | `get_table('SHARADAR/TICKERS', table='SEP', ticker='AAPL')` | `download_table("TICKERS", path, table="SEP", ticker="AAPL")` | — |
| 某表的字段说明 | `get_table('SHARADAR/INDICATORS', table='SEP')` | `download_table("INDICATORS", path, table="SEP")` | 10 |
| 指标：按 ticker | `get_table('SHARADAR/METRICS', ticker='SPY')` | `download_table("METRICS", path, ticker="SPY")` | 1（22 列） |

公司行为（ACTIONS）的操作见 [sharadar_fund_prices/README.md](../sharadar_fund_prices/README.md#操作对照)。Ticker 元数据和字段说明两项中的 `table="SEP"` 是 `TICKERS` / `INDICATORS` 表里的一列，不是函数的 `table` 参数。

### 不支持的操作

| 操作 | 原因 | 替代方式 |
|---|---|---|
| 表配置元数据 `.../SEP/metadata.json` | 这是 Web API 专用接口，不是数据表 | 「某表的字段说明」一项的 `INDICATORS` 已经给出列名、是否可过滤、是否主键 |
| JSON / XML 格式 | 只是 Web API 的输出格式，Python 端没有意义 | 统一输出 CSV（zip） |
