# Sharadar Core US Insiders Data 样本数据

| 表 | 主键 | 取样方式 | 频率 |
|---|---|---|---|
| `SF2.csv` | `ticker, filingdate, formtype, ownername, rownum` | 每种 `formtype` 各一行，另加同一份申报的第 2 个 `rownum` | event |

## 主键取值

- **SF2**：每行是内部人在一份 SEC 申报（Form 3/4/5）中的一条交易或持仓记录，只在申报日有记录。
  - `formtype` 有 6 种：`3`、`4`、`5`，以及申报被重述后的 `RESTATED - 3`、`RESTATED - 4`、`RESTATED - 5`。在 AAPL、MSFT、JPM、TSLA 的 20,000 行中，分别为 4（19,349）、3（451）、RESTATED - 4（89）、5（74）、RESTATED - 3（30）、RESTATED - 5（7）。
  - `rownum` 是同一内部人同一申报日内的记录序号。同一份申报包含多条记录时依次为 1、2、…（如 MSFT 的 MARQUARDT DAVID F 在 2008-01-02 的申报有 rownum 1、2 两行）。
  - `securityadcode` 有 6 种：D（衍生品，无交易）、DA（衍生品买入）、DD（衍生品卖出）、N（非衍生品，无交易）、NA（非衍生品买入）、ND（非衍生品卖出）。
  - AAPL 在 2024 年上半年共 71 行。

## 可过滤列

来自 `INDICATORS` 表（`isfilter = Y`、`isprimarykey = Y`）。只有可过滤列能出现在 `**filters` 中，其余列只能通过 `columns` 选取。完整列名见同目录 CSV 的表头。

### SF2

| 列 | 可过滤 | 主键 |
|---|---|---|
| `ticker` | ✅ | ✅ |
| `filingdate` | ✅ | ✅ |
| `formtype` | | ✅ |
| `ownername` | ✅ | ✅ |
| `securityadcode` | ✅ | |
| `transactionvalue` | ✅ | |
| `rownum` | | ✅ |
| issuername, officertitle, isdirector, isofficer, istenpercentowner, transactiondate, transactioncode, sharesownedbeforetransaction 等其余 17 列 | | |

主键中的 `formtype`、`rownum` 不能过滤；`transactiondate` 也不能过滤，按时间筛选用 `filingdate`。

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
| 多值 | `securityadcode=["NA", "ND"]` | `securityadcode=NA,ND` |
| 区间 | `filingdate={"gte": "2024-01-01", "lte": "2024-06-30"}` | `filingdate.gte=2024-01-01&filingdate.lte=2024-06-30` |

区间的键可用 `gt`、`gte`、`lt`、`lte`，日期格式为 `YYYY-MM-DD`。多个过滤条件之间是"且"的关系。

### 操作对照

| 操作 | 官方 Python 写法 | `download_table` 写法 | 实测行数 |
|---|---|---|---|
| 单个 ticker、申报日区间 | `get_table('SHARADAR/SF2', ticker='AAPL', filingdate={'gte':'2024-01-01','lte':'2024-06-30'})` | `download_table("SF2", path, ticker="AAPL", filingdate={"gte": "2024-01-01", "lte": "2024-06-30"})` | 71 |
| 多个 ticker 全部历史 | `get_table('SHARADAR/SF2', ticker=['AAPL','MSFT','JPM','TSLA'], paginate=True)` | `download_table("SF2", path, ticker=["AAPL", "MSFT", "JPM", "TSLA"])` | ≥ 20,000（`get` + `limit=20000` 时被截断） |
| 只看买卖交易 | `get_table('SHARADAR/SF2', ticker='AAPL', securityadcode=['NA','ND'])` | `download_table("SF2", path, ticker="AAPL", securityadcode=["NA", "ND"])` | — |
| 某表的字段说明 | `get_table('SHARADAR/INDICATORS', table='SF2')` | `download_table("INDICATORS", path, table="SF2")` | 24 |
| 超过 1 万行 | `get_table(..., paginate=True)` 或 `qopts.export=true` | 默认的 `method="export"` 即可，例如 `download_table("SF2", path)` 下载整表 | 无上限 |

### 不支持的操作

| 操作 | 原因 | 替代方式 |
|---|---|---|
| 表配置元数据 `.../SF2/metadata.json` | 这是 Web API 专用接口，不是数据表 | 「某表的字段说明」一项的 `INDICATORS` 已经给出列名、是否可过滤、是否主键 |
| JSON / XML 格式 | 只是 Web API 的输出格式，Python 端没有意义 | 统一输出 CSV（zip） |
