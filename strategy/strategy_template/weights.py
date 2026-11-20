'''
weights.py - Target weights of this strategy. Fill in the body of compute;
keep its name and arguments. strategy_example/weights.py is a full example.
'''

# %%
# Target Weights

# Target weights of every session
def compute(data, params):
    """
    Target weights of every session.

    Parameters
    ----------
    data : pd.DataFrame
        Prices from data.fetch. Index = session dates, Columns = symbols,
        values = config data.field.
    params : dict
        config.yaml params. Every parameter comes from here.

    Returns
    -------
    weights : pd.DataFrame
        Target fraction of capital, same index and columns as `data`: long > 0,
        short < 0, no position = 0. Row t uses data up to session t only.
    """

    # 1. Signal: one score per stock per session, e.g. signal = data.shift(skip) / data.shift(lookback) - 1

    # signal =

    # 2. Eligible: drop stocks without a price today or enough history, e.g. eligible_signal = signal.where(data.notna())

    # eligible_signal =

    # 3. Select: the stocks to hold, e.g. selected_asset = eligible_signal.rank(axis=1, ascending=False) <= top_n

    # selected_asset =

    # 4. Weights: e.g. selected_asset_rebalance_weights = selected_asset.div(selected_asset.sum(axis=1), axis=0) * gross, then fillna(0.0)

    # selected_asset_rebalance_weights =

    raise NotImplementedError("fill in compute in weights.py")
