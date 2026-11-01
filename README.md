# factor-based-strategies

因子策略研究项目。研究方法见 [research_spec.md](research_spec.md)，各章节对应的代码文件见 [architecture.md](architecture.md)。

### 准备

按顺序执行：

```bash
# 1. 下载代码
git clone https://github.com/shjunz/factor-based-strategies.git
cd factor-based-strategies

# 2. 创建虚拟环境 .venv，安装 fbs 包和全部依赖
make install

# 3. 生成 .env，再打开 .env 填入 API key（等号两边不要有空格）
make env

# 4. 启动后端
make api
```

第 4 步启动后，打开 http://127.0.0.1:8000/docs 可以看到全部接口(按 Ctrl+C 停止) 

**下载数据只用 `POST /api/downloads` 这一个接口。** 步骤：

1. 展开 `downloads` 下的 `POST /api/downloads`，点 **Try it out**
2. Request body 里已经填好一个能直接运行的模板（SPY 在 2024 年 1 月的 SFP 日线），按需要修改后点 **Execute**：

   ```json
   {
     "product": "fund_prices",
     "table": "SFP",
     "filters": {"ticker": "SPY", "date": {"gte": "2024-01-01", "lte": "2024-01-31"}}
   }
   ```

3. 返回结果里有 `job_id`。用 `GET /api/downloads/{job_id}` 查进度：`status` 变成 `done` 后，`path` 就是文件位置

请求参数：

| 参数 | 是否必填 | 含义 | 取值 |
|---|---|---|---|
| `product` | 必填 | 产品 | `core_us_fundamentals`、`core_us_insiders`、`core_us_institutional_investors`、`equity_prices`、`fund_prices` 五个之一 |
| `table` | 必填 | 表代码，必须属于 `product` | `GET /api/tables` 列出每个产品有哪些表；各表的含义见 [data/data_library.md](data/data_library.md) |
| `filters` | 选填 | 按列过滤，不填就是下载整张表 | 只有可过滤列能用，见 `GET /api/tables/{table}/schema` 返回的 `filters`，或 [data/bronze/sample/](data/bronze/sample/) 下各产品 README 的“可过滤列” |
| `columns` | 选填 | 只下载这些列，不填就是全部列 | `GET /api/tables/{table}/schema` 返回的 `columns`，或 sample 目录下同名 CSV 的表头 |
| `limit` | 选填 | 最多下载多少行，不填就是全部 | 正整数或不填，试跑时用 `1` 或 `10` |
| `overwrite` | 选填，默认 `false` | 当天已经下载过同样的文件时，是否重新下载 | `true` / `false` |

`filters` 中每一列的值有三种写法：

| 写法 | 例子 |
|---|---|
| 单个值 | `"ticker": "SPY"` |
| 多个值 | `"ticker": ["SPY", "QQQ"]` |
| 范围，可用 `gt`、`gte`、`lt`、`lte`，日期写成 `YYYY-MM-DD` | `"date": {"gte": "2024-01-01", "lte": "2024-01-31"}` |



## 常用命令

`make help` 列出全部命令。

| 命令 | 作用 |
|---|---|
| `make install` | 创建 `.venv`（只在第一次创建），安装 fbs 包和依赖 |
| `make env` | 从 `.env.example` 生成 `.env`，已存在时不覆盖 |
| `make api` | 启动后端，修改代码后自动重启，只能本机访问 |
| `make api-prod` | 启动后端，不自动重启，其他机器也能访问（部署用） |
| `make api PORT=9000` | 换端口启动 |
| `make clean-bronze` | 删除 `data/bronze/` 中下载的数据，保留 `sample/`，执行前需要输入 `y` 确认 |
| `make clean` | 删除 `.venv` 和构建产物，之后需要重新 `make install` |

## 目录

| 目录 | 内容 |
|---|---|
| `src/fbs/etl/` | M1 数据 ETL：提取、变换、存储 |
| `src/fbs/api/` | 后端 API，M1 数据下载的一层封装 |
| `src/fbs/eval/` | M3 因子研究与评价 |
| `data/bronze/` | 原始数据；只有 `sample/` 提交到 GitHub |
| `data/silver/`、`data/gold/` | 中间数据、清洗数据，只保存在本地 |
