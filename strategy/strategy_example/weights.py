'''
weights.py - strategy_example target weights: equal weight on the top_n
stocks by 12-1 momentum, long only.
'''

# %%
# Target Weights

# Target weights of every session
def compute(data, params):
    """
    Target weights of every session: equal weight on the top_n stocks by
    momentum from t-lookback to t-skip.

    Parameters
    ----------
    data : pd.DataFrame
        Prices from data.fetch. Index = session dates, Columns = symbols.
    params : dict
        config.yaml params: lookback, skip, top_n, gross.

    Returns
    -------
    weights : pd.DataFrame
        Target fraction of capital, same index and columns as `data`. Row t
        uses data up to session t only.
    """

    # 1. Signal: Calculate 12-1 momentum signal
    signal = data.shift(params["skip"]) / data.shift(params["lookback"]) - 1

    # 2. Eligible: keep the signal only where the stock has a price at t
    eligible_signal = signal.where(data.notna())

    # 3. Select: True for the top_n stocks by eligible_signal each session
    selected_asset = eligible_signal.rank(axis=1, ascending=False, method="first") <= params["top_n"]

    # 4. Weights: equal weight on selected_asset, gross in total, 0 for the rest
    selected_asset_rebalance_weights = selected_asset.div(selected_asset.sum(axis=1), axis=0) * params["gross"]
    selected_asset_rebalance_weights = selected_asset_rebalance_weights.fillna(0.0)

    return selected_asset_rebalance_weights
