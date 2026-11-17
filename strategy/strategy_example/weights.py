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

    # 1. Signal: return from t-lookback to t-skip
    momentum = data.shift(params["skip"]) / data.shift(params["lookback"]) - 1

    # 2. Eligible: a price today and a full history
    momentum = momentum.where(data.notna())

    # 3. Select: the top_n by momentum
    selected = momentum.rank(axis=1, ascending=False, method="first") <= params["top_n"]

    # 4. Weights: equal weight, gross in total, 0 for the rest
    weights = selected.div(selected.sum(axis=1), axis=0) * params["gross"]
    weights = weights.fillna(0.0)

    return weights
