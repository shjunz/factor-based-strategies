"""Target weights for this strategy. Replace the body of compute(); keep its name and signature.

Contract: compute(data, params) -> DataFrame
    index   = session dates (same as data), columns = symbols
    values  = target fraction of capital (long > 0, short < 0, 0 = no position)
    row t   = uses only data up to and including session t (no look-ahead)
    The backtest uses every row; the paper runner uses the row of the signal session.
    All parameters come from config.yaml `params`.
"""

from __future__ import annotations

import pandas as pd


def compute(data: pd.DataFrame, params: dict) -> pd.DataFrame:
    # TODO: signal -> weights
    raise NotImplementedError("fill in weights.py: compute(data, params)")
