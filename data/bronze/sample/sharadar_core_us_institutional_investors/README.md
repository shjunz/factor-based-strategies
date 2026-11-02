# Sharadar Core US Institutional Investors Data 样本数据

| 表 | 主键 | 取样方式 | 频率 |
|---|---|---|---|
| `SF3.csv` | `ticker, investorid, securitytype, date` | 2024-03-31 每种 `securitytype` 各一行 | quarterly |
| `SF3A.csv` | `date, ticker` | AAPL 最近 4 个季度 | quarterly |
| `SF3B.csv` | `date, investorid` | 2024-03-31 的 3 个机构 | quarterly |

## 主键取值

- **SF3**：机构投资者 13F 持仓明细，每个机构每个季度对每个 ticker 的每种证券类型一行。`date` 是日历季度末。
  - `securitytype` 有 8 种：SHR（普通股）、FND（基金份额）、CLL（看涨期权）、PUT（看跌期权）、WNT（权证）、DBT（债券）、PRF（优先股）、UND（未识别类型）。
  - AAPL 在 2024-03-31 一个季度就超过 5,000 行（每个持仓机构 × 证券类型一行）。
- **SF3A**：SF3 按 ticker 汇总，每个 ticker 每个季度一行（持有机构数、持仓量等）。AAPL 共 54 个季度。最近一个季度（2026-09-30）的 `shrholders` 只有 2,916，上一季度为 6,174，是因为 13F 在季度结束后 45 天内提交，最新季度的数据还不完整。
- **SF3B**：SF3 按机构汇总，每个机构每个季度一行。`investorid` 是固定的 6 位机构代码，在 SF3 和 SF3B 中通用。2024-03-31 一个季度就超过 5,000 个机构。

## 可过滤列

来自 `INDICATORS` 表（`isfilter = Y`、`isprimarykey = Y`）。只有可过滤列能出现在 `**filters` 中，其余列只能通过 `columns` 选取。完整列名见同目录 CSV 的表头。

### SF3

| 列 | 可过滤 | 主键 |
|---|---|---|
| `ticker` | ✅ | ✅ |
| `investorid` | ✅ | ✅ |
| `securitytype` | ✅ | ✅ |
| `date` | ✅ | ✅ |
| `value, units` | | |

### SF3A

| 列 | 可过滤 | 主键 |
|---|---|---|
| `date` | ✅ | ✅ |
| `ticker` | ✅ | ✅ |
| shrunits, cllunits, name, shrholders, cllholders, putholders, wntholders, dbtholders 等其余 27 列 | | |

### SF3B

| 列 | 可过滤 | 主键 |
|---|---|---|
| `date` | ✅ | ✅ |
| `investorid` | ✅ | ✅ |
| investorname, shrholdings, cllholdings, putholdings, wntholdings, dbtholdings, prfholdings, fndholdings 等其余 27 列 | | |

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
| 单值 | `date="2024-03-31"` | `date=2024-03-31` |
| 多值 | `securitytype=["CLL", "PUT"]` | `securitytype=CLL,PUT` |
| 区间 | `date={"gte": "2023-01-01", "lte": "2023-12-31"}` | `date.gte=2023-01-01&date.lte=2023-12-31` |

区间的键可用 `gt`、`gte`、`lt`、`lte`，日期格式为 `YYYY-MM-DD`。`date` 只有季度末有数据。多个过滤条件之间是"且"的关系。

### 操作对照

| 操作 | 官方 Python 写法 | `download_table` 写法 | 实测行数 |
|---|---|---|---|
| 持仓明细：单个 ticker 单季度 | `get_table('SHARADAR/SF3', ticker='AAPL', date='2024-03-31', paginate=True)` | `download_table("SF3", path, ticker="AAPL", date="2024-03-31")` | ≥ 5,000（`get` + `limit=5000` 时被截断） |
| 持仓明细：按证券类型 | `get_table('SHARADAR/SF3', securitytype='FND', date='2024-03-31')` | `download_table("SF3", path, securitytype="FND", date="2024-03-31")` | — |
| 按 ticker 汇总：全部季度 | `get_table('SHARADAR/SF3A', ticker='AAPL')` | `download_table("SF3A", path, ticker="AAPL")` | 54 |
| 按机构汇总：单季度 | `get_table('SHARADAR/SF3B', date='2024-03-31', paginate=True)` | `download_table("SF3B", path, date="2024-03-31")` | ≥ 5,000（`get` + `limit=5000` 时被截断） |
| 某表的字段说明 | `get_table('SHARADAR/INDICATORS', table='SF3')` | `download_table("INDICATORS", path, table="SF3")` | 6 |
| 超过 1 万行 | `get_table(..., paginate=True)` 或 `qopts.export=true` | 默认的 `method="export"` 即可，例如 `download_table("SF3", path)` 下载整表 | 无上限 |

### 不支持的操作

| 操作 | 原因 | 替代方式 |
|---|---|---|
| 表配置元数据 `.../SF3/metadata.json` | 这是 Web API 专用接口，不是数据表 | 「某表的字段说明」一项的 `INDICATORS` 已经给出列名、是否可过滤、是否主键 |
| JSON / XML 格式 | 只是 Web API 的输出格式，Python 端没有意义 | 统一输出 CSV（zip） |
