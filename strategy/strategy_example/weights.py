"""strategy_example target weights: equal-weight top-N by 12-1 momentum, long only.

Contract: compute(data, params) -> DataFrame
    index   = session dates (same as data), columns = symbols
    values  = target fraction of capital (long > 0, short < 0, 0 = no position)
    row t   = uses only data up to and including session t
The backtest uses every row; the paper runner uses the row of the signal session.
"""

from __future__ import annotations

import pandas as pd


def compute(data: pd.DataFrame, params: dict) -> pd.DataFrame:
    lookback, skip = int(params["lookback"]), int(params["skip"])
    top_n, gross = int(params["top_n"]), float(params["gross"])

    momentum = data.shift(skip) / data.shift(lookback) - 1           # return from t-252 to t-21
    eligible = momentum.notna() & data.notna()                       # needs a price today and a full history
    rank = momentum.where(eligible).rank(axis=1, ascending=False, method="first")
    selected = rank <= top_n

    count = selected.sum(axis=1)
    weights = selected.astype(float).div(count.where(count > 0), axis=0) * gross
    return weights.fillna(0.0)
