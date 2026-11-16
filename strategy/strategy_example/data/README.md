# data

strategy_example 的数据存放位置，由 data.py 每次运行时自动写入，不需要手动准备文件。

- bronze/sharadar_equity_prices/：从 Sharadar 下载的原始 SEP 和 TICKERS 文件（research_spec.md M1.1.3）
- gold/EQ/spot/daily/：清洗后的 gold 文件（research_spec.md M1.3）；gold/instrument_map.csv 记录股票代码与 instrument_id 的对应
- 本文件夹中除本 README 外的所有文件都不会提交到 git，每位研究员保存自己的一份
