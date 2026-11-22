'''
data_freshness.py - risk_input_data: the strategy's data is not empty and
reaches the signal session.
'''

# %%
# Imports

import pandas as pd

# %%
# Checks

# Data check
def risk_input_data(data, signal_session):
    """
    Check the data is not empty and includes the signal session.

    Parameters
    ----------
    data : pd.DataFrame
        Output of the strategy's data.fetch. Index = session dates.
    signal_session : date
        Session the weights are computed for.

    Returns
    -------
    failures : list of str
        Empty if the data is usable.

    Examples
    --------
    >>> from datetime import date
    >>> data = pd.DataFrame({"SPY": [470.0, 472.0]},
    ...                     index=pd.to_datetime(["2024-01-02", "2024-01-03"]))
    >>> risk_input_data(data, date(2024, 1, 3))
    []
    >>> risk_input_data(data, date(2024, 1, 4))
    ['stale data: last session 2024-01-03, expected 2024-01-04']
    """

    # No rows at all
    if data.empty:
        return ["data is empty"]

    # Last row must be the signal session, else the source has not published it yet
    last = pd.Timestamp(data.index.max()).date()
    if last != signal_session:
        return [f"stale data: last session {last}, expected {signal_session}"]

    return []
