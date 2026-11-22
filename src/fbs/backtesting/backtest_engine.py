'''
backtest_engine.py - backtest: daily strategy and equal-weight benchmark
returns of the target weights, and one-way turnover.

Timing matches the live runner: weights of signal session t are bought at the
close of t+1 (market-on-close), so they earn returns from session t+2 on.
Weights are refreshed only on the config.yaml rebalance sessions and held in
between (no intra-period drift, no costs).
'''

# %%
# Imports

import pandas as pd

from fbs.execution import execution_rebalance_sessions

# %%
# Backtest

# Daily backtest returns
def backtest(prices, weights, rule):
    """
    Daily strategy and equal-weight benchmark returns, and one-way turnover.

    Parameters
    ----------
    prices : pd.DataFrame
        Prices from data.fetch. Index = session dates, Columns = symbols.
    weights : pd.DataFrame
        Target weights from weights.compute, same shape as `prices`.
    rule : {"D", "W", "M"}
        config.yaml rebalance.

    Returns
    -------
    bt : pd.DataFrame
        Index = session dates from the first invested session + 2, Columns =
        strategy, benchmark (daily returns) and turnover.

    Examples
    --------
    >>> idx = pd.bdate_range("2024-01-01", periods=5)
    >>> prices = pd.DataFrame({"SPY": [100, 101, 102, 101, 103],
    ...                        "QQQ": [50, 50, 51, 52, 52]}, index=idx)
    >>> weights = pd.DataFrame({"SPY": [0, 1, 1, 0.5, 0.5],
    ...                         "QQQ": [0, 0, 0, 0.5, 0.5]}, index=idx)
    >>> backtest(prices, weights, "D").round(4)
                strategy  benchmark  turnover
    2024-01-04   -0.0098     0.0049       0.0
    2024-01-05    0.0198     0.0099       0.5
    """

    # Daily returns
    rets = prices.astype(float).pct_change(fill_method=None)

    # Held weights: refreshed on rebalance sessions, carried forward in between
    sessions = list(weights.index.date)
    is_rebalance = pd.Series(weights.index.date, index=weights.index).isin(execution_rebalance_sessions(sessions, rule))
    held = weights.where(is_rebalance, axis=0).ffill().fillna(0.0).reindex(columns=rets.columns, fill_value=0.0)

    # Weights of t earn the return of t+2 (bought at the close of t+1)
    bt = pd.DataFrame({
        "strategy": (held.shift(2) * rets.fillna(0.0)).sum(axis=1),
        "benchmark": rets.mean(axis=1),
        "turnover": held.diff().abs().sum(axis=1).shift(1) / 2,
    })

    # Start once the strategy holds anything
    invested = held.abs().sum(axis=1) > 0
    if not invested.any():
        return bt.iloc[0:0]
    bt = bt.loc[invested.idxmax():].iloc[2:].fillna(0.0)

    return bt
