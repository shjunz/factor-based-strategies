# Sharadar Core US Fundamentals Data 样本数据

| 表 | 主键 | 取样方式 | 频率 |
|---|---|---|---|
| `SF1.csv` | `ticker, dimension, datekey, reportperiod` | AAPL 在 `calendardate = 2023-12-31` 的 6 种 `dimension` 各一行 | quarterly / annual / ttm（由 `dimension` 决定） |
| `DAILY.csv` | `ticker, date` | AAPL、MSFT 在 2024-01-02 至 2024-01-05 的 4 个交易日 | daily |
| `SP500.csv` | `date, action, ticker` | 每种 `action` 各一行，added 与 removed 取同一次调换 | event（added、removed）+ snapshot（historical、current） |
| `EVENTS.csv` | `date, ticker` | AAPL 的 2 个单一事件和 1 个多事件日 | event |
| `TICKERS.csv` | `table, permaticker, ticker` | 与 Sharadar Fund Prices 共用同一张表，样本相同 | snapshot |
| `INDICATORS.csv` | `table, indicator` | 与 Sharadar Fund Prices 共用同一张表，样本相同 | snapshot |
| `ACTIONS.csv` | `date, action, ticker, name, contraticker, contraname` | 与 Sharadar Fund Prices 共用同一张表，样本相同 | event |

## 主键取值

- **SF1**：`dimension` 有 6 种：ARQ（季度，不含重述）、MRQ（季度，含重述）、ARY（年度，不含重述）、MRY（年度，含重述）、ART（滚动 12 个月，不含重述）、MRT（滚动 12 个月，含重述）。AAPL 在 2023 年共 18 行：4 种季度和 TTM 维度各 4 行，2 种年度维度各 1 行。
  - `calendardate` 是归一化后的日历季度末，`reportperiod` 是公司实际的财报期末。AAPL 财年截至 9 月，所以 `calendardate = 2023-12-31` 的年度行对应的是 `reportperiod = 2023-09-30`、`fiscalperiod = 2023-FY`。
  - `datekey` 在 AR 维度上是财报提交日（如 ARQ 为 2024-02-02），在 MR 维度上等于 `reportperiod`（如 MRQ 为 2023-12-30）。回测时用 MR 维度的 `datekey` 作为数据可用日期会有前视偏差，应使用 AR 维度。
- **DAILY**：每个 `ticker` 每个交易日一行，是基于价格的估值指标（ev、evebit、evebitda、marketcap、pb、pe、ps）。2024 年 1 月 AAPL 共 21 行，正好是当月全部交易日。
- **SP500**：`action` 有 4 种。
  - `historical`：每个季度末一份完整的成分股名单，2023–2024 年共 8 个季度末，每期 503 或 504 行。
  - `current`：当前成分股名单，`date` 是数据刷新日（2026-10-31）。
  - `added` / `removed`：成分股调入和调出，`date` 是生效日而不是公告日。同一次调换通过 `contraticker` 互相指向，两边的日期可能不同（GEHC 2023-01-04 调入，VNO 2023-01-05 调出）。
- **EVENTS**：每个 `ticker` 每天最多一行。同一天发生多个事件时合并为一行，`eventcodes` 用 `|` 分隔（如 `81|91`）。代码含义见 INDICATORS 中 `table = EVENTCODES` 的 37 行。AAPL 共 322 行，从 1994-02-10 到 2026-09-01。
- **TICKERS、INDICATORS、ACTIONS**：与 Sharadar Fund Prices 是同一张表，代码相同，只需下载一次。主键取值见 [sharadar_fund_prices/README.md](../sharadar_fund_prices/README.md#主键取值)。TICKERS 中本产品对应 `table = SF1` 的行。

## 可过滤列

来自 `INDICATORS` 表（`isfilter = Y`、`isprimarykey = Y`）。只有可过滤列能出现在 `**filters` 中，其余列只能通过 `columns` 选取。完整列名见同目录 CSV 的表头。

### SF1

| 列 | 可过滤 | 主键 |
|---|---|---|
| `ticker` | ✅ | ✅ |
| `dimension` | ✅ | ✅ |
| `calendardate` | ✅ | |
| `datekey` | | ✅ |
| `reportperiod` | | ✅ |
| `lastupdated` | ✅ | |
| revenue, cor, sgna, rnd, opex, intexp, taxexp, netincdis 等其余 106 列 | | |

主键中的 `datekey`、`reportperiod` 不能过滤，按时间筛选用 `calendardate`。

### DAILY

| 列 | 可过滤 | 主键 |
|---|---|---|
| `ticker` | ✅ | ✅ |
| `date` | ✅ | ✅ |
| `lastupdated` | ✅ | |
| `ev, evebit, evebitda, marketcap, pb, pe, ps` | | |

### SP500

| 列 | 可过滤 | 主键 |
|---|---|---|
| `date` | ✅ | ✅ |
| `action` | ✅ | ✅ |
| `ticker` | ✅ | ✅ |
| `contraticker` | ✅ | |
| `name, contraname, note` | | |

### EVENTS

| 列 | 可过滤 | 主键 |
|---|---|---|
| `date` | ✅ | ✅ |
| `ticker` | ✅ | ✅ |
| `eventcodes` | | |

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
| 多值 | `dimension=["ARQ", "ART"]` | `dimension=ARQ,ART` |
| 区间 | `calendardate={"gte": "2023-01-01", "lte": "2023-12-31"}` | `calendardate.gte=2023-01-01&calendardate.lte=2023-12-31` |

区间的键可用 `gt`、`gte`、`lt`、`lte`，日期格式为 `YYYY-MM-DD`。多个过滤条件之间是"且"的关系。

### 操作对照

| 操作 | 官方 Python 写法 | `download_table` 写法 | 实测行数 |
|---|---|---|---|
| 财报：单个 ticker 一年 | `get_table('SHARADAR/SF1', ticker='AAPL', calendardate={'gte':'2023-01-01','lte':'2023-12-31'})` | `download_table("SF1", path, ticker="AAPL", calendardate={"gte": "2023-01-01", "lte": "2023-12-31"})` | 18（112 列） |
| 财报：只取一种维度 | `get_table('SHARADAR/SF1', ticker='AAPL', dimension='ARQ', ...)` | `download_table("SF1", path, ticker="AAPL", dimension="ARQ", calendardate={"gte": "2023-01-01", "lte": "2023-12-31"})` | 4 |
| 每日估值：日期区间 | `get_table('SHARADAR/DAILY', ticker='AAPL', date={'gte':'2024-01-01','lte':'2024-01-31'})` | `download_table("DAILY", path, ticker="AAPL", date={"gte": "2024-01-01", "lte": "2024-01-31"})` | 21 |
| 标普 500 成分：日期区间 | `get_table('SHARADAR/SP500', date={'gte':'2023-01-01','lte':'2024-12-31'})` | `download_table("SP500", path, date={"gte": "2023-01-01", "lte": "2024-12-31"})` | 4,089 |
| 标普 500 当前成分 | `get_table('SHARADAR/SP500', action='current')` | `download_table("SP500", path, action="current")` | — |
| 重大事件：按 ticker | `get_table('SHARADAR/EVENTS', ticker='AAPL')` | `download_table("EVENTS", path, ticker="AAPL")` | 322 |
| 事件代码含义 | `get_table('SHARADAR/INDICATORS', table='EVENTCODES')` | `download_table("INDICATORS", path, table="EVENTCODES")` | 37 |
| 某表的字段说明 | `get_table('SHARADAR/INDICATORS', table='SF1')` | `download_table("INDICATORS", path, table="SF1")` | 112 |
| 超过 1 万行 | `get_table(..., paginate=True)` 或 `qopts.export=true` | 默认的 `method="export"` 即可，例如 `download_table("SF1", path)` 下载整表 | 无上限 |

「只取一种维度」的 4 行是「单个 ticker 一年」18 行中 ARQ 的部分。Ticker 元数据和公司行为（ACTIONS）的操作见 [sharadar_fund_prices/README.md](../sharadar_fund_prices/README.md#操作对照)。

### 不支持的操作

| 操作 | 原因 | 替代方式 |
|---|---|---|
| 表配置元数据 `.../SF1/metadata.json` | 这是 Web API 专用接口，不是数据表 | 「某表的字段说明」一项的 `INDICATORS` 已经给出列名、是否可过滤、是否主键 |
| JSON / XML 格式 | 只是 Web API 的输出格式，Python 端没有意义 | 统一输出 CSV（zip） |
