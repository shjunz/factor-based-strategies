'''
returns.py

'''

# %%
# Imports

import numpy as np
import pandas as pd

# %%
# Forward Returns

# Forward returns r(k)
def forward_returns(close, horizon=0):
    """
    Forward returns r(k) for k = 0..H, from the close of bar t+k to the close of
    bar t+k+1.

    Parameters
    ----------
    close : pd.DataFrame
        Adjusted close prices. Index = timestamp, Columns = symbol.
    horizon : int
        Largest k.

    Returns
    -------
    fwd_rets : pd.DataFrame
        Forward returns. Index = timestamp, Columns = (k, symbol).
    """

    fwd_rets = {}
    for k in range(horizon + 1):
        # Close of bar t+k and bar t+k+1
        start = close.shift(-k)
        end = close.shift(-(k + 1))
        fwd_rets[k] = end / start - 1
    fwd_rets = pd.concat(fwd_rets, axis=1)

    return fwd_rets

# %%
# Volatility Adjustment

# Volatility-adjusted forward returns
def vol_adjusted_returns(fwd_ret, close, sigma_tgt, window, bars_per_year):
    """
    Forward returns scaled to the target volatility.

    Parameters
    ----------
    fwd_ret : pd.DataFrame
        Forward returns. Index = timestamp, Columns = symbol.
    close : pd.DataFrame
        Adjusted close prices. Index = timestamp, Columns = symbol.
    sigma_tgt : float
        Annualized target volatility.
    window : int
        Number of lookback bars for historical volatility.
    bars_per_year : float
        Number of bars per year.

    Returns
    -------
    adj_ret : pd.DataFrame
        Volatility-adjusted forward returns. Index = timestamp, Columns = symbol.
    """

    # Return of each bar
    ret = close.pct_change(fill_method=None)

    # Annualized historical volatility from bars t-window+1..t
    sigma = ret.rolling(window).std() * np.sqrt(bars_per_year)

    # Scale forward returns
    adj_ret = fwd_ret * (sigma_tgt / sigma.where(sigma > 0))

    return adj_ret