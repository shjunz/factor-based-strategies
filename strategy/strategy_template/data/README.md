# data

strategy_template 的数据存放位置，由 data.py 自动写入，不需要手动准备文件。

数据按增量更新：第一次运行下载 universe 从回看起点开始的全部历史；之后每次只下载本地缺少的部分——新加入 universe 的股票、比本地更早的日期，以及 Sharadar 自上次同步以来更新过的行（新的交易日，以及因拆股、分红被修订的历史复权价，按 lastupdated 筛选）。下载的行覆盖本地同一交易日、同一股票的旧行。

- bronze/sharadar_equity_prices/：从 Sharadar 下载的原始 SEP 和 TICKERS 文件（research_spec.md M1.1.3）
- bronze/ 中每次增量下载各存一个文件，作为原始记录保留
- gold/EQ/spot/daily/sharadar_SEP_{clean_date}.parquet：清洗后的全部历史（research_spec.md M1.3），只保留最新一份，策略的训练和回测数据都从这里取
- gold/instrument_map.csv：股票代码与 instrument_id 的对应，已有的股票不再重新查询
- sync_state.json：上次同步日期（synced）和每只股票本地数据的起始日（coverage）；删掉它，下次运行会重新全量下载
- 本文件夹中除本 README 外的所有文件都不会提交到 git，每位研究员保存自己的一份
