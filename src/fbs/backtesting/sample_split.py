'''
sample_split.py - split_segments: label each backtest session IS, Embargo or
OOS by config.yaml split.
'''

# %%
# Imports

import numpy as np
import pandas as pd

# %%
# Segments

# IS / Embargo / OOS segments of a backtest
def split_segments(bt, split):
    """
    Label each backtest session IS, Embargo or OOS by config.yaml split.

    IS      = sessions up to split.is_end
    Embargo = the next split.embargo_sessions sessions, not evaluated
    OOS     = every later session, report only

    Parameters
    ----------
    bt : pd.DataFrame
        Output of backtest.
    split : dict or None
        config.yaml split: is_end, embargo_sessions. None for no split.

    Returns
    -------
    segments : pd.Series
        Index = bt.index, values "IS", "Embargo", "OOS"; all "Full" without a split.

    Examples
    --------
    >>> bt = pd.DataFrame({"strategy": 0.0},
    ...                   index=pd.bdate_range("2024-01-01", periods=5))
    >>> split_segments(bt, {"is_end": "2024-01-02", "embargo_sessions": 1}).tolist()
    ['IS', 'IS', 'Embargo', 'OOS', 'OOS']
    >>> split_segments(bt, None).unique().tolist()
    ['Full']
    """

    if not split:
        return pd.Series("Full", index=bt.index)

    is_mask = bt.index <= pd.Timestamp(split["is_end"])
    position = np.cumsum(~is_mask)   # 1 for the first session after is_end
    segments = np.where(is_mask, "IS",
                        np.where(position <= int(split["embargo_sessions"]), "Embargo", "OOS"))

    return pd.Series(segments, index=bt.index)
