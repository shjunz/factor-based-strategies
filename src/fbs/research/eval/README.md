# fbs.research.eval：因子评价（C4 L4）

横截面因子的标准评价指标，用于因子研究。它是共享库，自己不运行；计划让 [fbs.backtesting](../../backtesting/README.md) 和 [fbs.live](../../live/README.md) 的报告也改用这里的指标，现在还没接上。

上级图（策略研究的 L3）见 [src/fbs/research/README.md](../README.md)。

## L4 函数

全部在 [cs/metrics.py](cs/metrics.py)（cs = 横截面）。输入的前向收益由 [fbs.sample](../../sample/returns.py) 的 `forward_returns`、`vol_adjusted_returns` 算出。

| 指标 | 函数 | 做什么 |
| --- | --- | --- |
| Rank IC | `rank_ic`、`summary_rankic`、`nw_lag`、`nw_test` | Rank IC 及其 Newey-West 检验 |
| 分组收益 | `bucket_returns`、`quantile_spread`、`summary_spread`、`reverse_check`、`u_shape_check` | 分组收益、多空价差、方向和 U 形检查 |
| Fama-MacBeth | `fama_macbeth`、`summary_fama_macbeth` | Fama-MacBeth 回归 |
| IC 衰减 | `ic_decay`、`ic_half_life` | IC 衰减和半衰期 |
| 换手 | `quantile_turnover`、`summary_turnover` | 分组换手 |
| 风险画像 | `quantile_cvar`、`quantile_equity`、`quantile_sharpe`、`quantile_max_drawdown`、`risk_profile` | 尾部风险、净值、Sharpe、回撤、风险因子暴露 |
