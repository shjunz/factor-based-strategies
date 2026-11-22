'''
performance_metrics.py - metrics: annual return, annual volatility, Sharpe and
maximum drawdown of daily returns.
'''

# %%
# Imports

import numpy as np

# %%
# Constants

# Sessions per year, for annualising
BARS_PER_YEAR = 252

# %%
# Metrics

# Performance metrics
def metrics(r):
    """
    Annual return, annual volatility, Sharpe and maximum drawdown.

    Parameters
    ----------
    r : pd.Series
        Daily returns.

    Returns
    -------
    m : dict of str to float
        The four metrics, all NaN for fewer than 2 returns or zero volatility.

    Examples
    --------
    >>> import pandas as pd
    >>> m = metrics(pd.Series([0.01, -0.02, 0.015, 0.005]))
    >>> {k: round(float(v), 4) for k, v in m.items()}
    {'Annual return': 0.8336, 'Annual vol': 0.2468, 'Sharpe': 2.5529, 'Max drawdown': -0.02}
    >>> metrics(pd.Series([0.01]))["Sharpe"]
    nan
    """

    # Not enough data
    if len(r) < 2 or r.std() == 0:
        return {"Annual return": np.nan, "Annual vol": np.nan, "Sharpe": np.nan, "Max drawdown": np.nan}

    equity = (1 + r).cumprod()
    m = {
        "Annual return": equity.iloc[-1] ** (BARS_PER_YEAR / len(r)) - 1,
        "Annual vol": r.std() * np.sqrt(BARS_PER_YEAR),
        "Sharpe": r.mean() / r.std() * np.sqrt(BARS_PER_YEAR),
        "Max drawdown": (equity / equity.cummax() - 1).min(),
    }

    return m
