'''
tradable_assets.py - execution_remove_invalid_assets: drop NaN, dust,
untradable symbols and disallowed shorts from the target weights.
'''

# %%
# Constants

# Weights smaller than this are treated as 0
DUST_WEIGHT = 1e-6

# %%
# Targets

# Tradable target weights
def execution_remove_invalid_assets(weights, assets, allow_shorts):
    """
    Drop NaN, dust, untradable symbols and disallowed shorts from the target
    weights.

    Parameters
    ----------
    weights : pd.Series
        Target weight per symbol.
    assets : dict of str to AssetInfo
        Alpaca permissions per symbol.
    allow_shorts : bool
        config.yaml paper.limits allow_shorts.

    Returns
    -------
    targets : dict of str to float
        Weights that can be traded.
    notes : list of str
        One line per dropped symbol.

    Examples
    --------
    >>> import pandas as pd
    >>> from fbs.live.broker import AssetInfo
    >>> assets = {"SPY": AssetInfo(tradable=True, shortable=True, easy_to_borrow=True),
    ...           "XYZ": AssetInfo(tradable=False, shortable=False, easy_to_borrow=False),
    ...           "GME": AssetInfo(tradable=True, shortable=True, easy_to_borrow=False)}
    >>> weights = pd.Series({"SPY": 0.6, "XYZ": 0.2, "GME": -0.2, "QQQ": float("nan")})
    >>> targets, notes = execution_remove_invalid_assets(weights, assets, allow_shorts=True)
    >>> targets
    {'SPY': 0.6}
    >>> notes
    ['XYZ: not tradable on Alpaca, target set to 0', 'GME: short not allowed or not borrowable, target set to 0']
    """

    targets, notes = {}, []
    for symbol, w in weights.dropna().items():
        w = float(w)

        # Dust
        if abs(w) < DUST_WEIGHT:
            continue

        # Not tradable on Alpaca
        info = assets.get(symbol)
        if info is None or not info.tradable:
            notes.append(f"{symbol}: not tradable on Alpaca, target set to 0")
            continue

        # Short not allowed or not borrowable
        if w < 0 and not (allow_shorts and info.shortable and info.easy_to_borrow):
            notes.append(f"{symbol}: short not allowed or not borrowable, target set to 0")
            continue

        targets[symbol] = w

    return targets, notes
