'''
identifiers.py - Instrument identifiers from the data source's permanent IDs.
'''

# %%
# Imports

import pandas as pd

# %%
# Instrument ID

# Sharadar instrument ID
def add_instrument_id(raw, tickers, table):
    """
    Sharadar raw data with an instrument_id column, taken from the permaticker
    of each ticker in the TICKERS table.

    Parameters
    ----------
    raw : pd.DataFrame
        Raw data of one Sharadar table, with ticker and date columns.
    tickers : pd.DataFrame
        Sharadar TICKERS table, with table, ticker and permaticker columns.
    table : str
        Sharadar table name of the raw data, such as SEP.

    Returns
    -------
    with_id : pd.DataFrame
        Raw data with an instrument_id column.

    Raises
    ------
    ValueError
        If a ticker appears more than once in TICKERS for the table, a row has
        no instrument_id, or (instrument_id, date) is not unique.
    """

    # Ticker to permaticker for this table, one row per ticker
    ids = tickers.loc[tickers["table"] == table, ["ticker", "permaticker"]]
    dup_tickers = ids.loc[ids["ticker"].duplicated(), "ticker"]
    if not dup_tickers.empty:
        raise ValueError(f"tickers repeated in TICKERS for {table}: "
                         f"{dup_tickers.unique()[:10].tolist()}")

    # Permaticker merged by ticker as instrument_id
    ids = ids.rename(columns={"permaticker": "instrument_id"})
    with_id = raw.merge(ids, on="ticker", how="left", validate="many_to_one")

    # Every row has an instrument_id
    missing = with_id["instrument_id"].isna()
    if missing.any():
        raise ValueError(f"{missing.sum()} rows have no instrument_id, tickers: "
                         f"{with_id.loc[missing, 'ticker'].unique()[:10].tolist()}")

    # One row per (instrument_id, date)
    dup_rows = with_id.duplicated(["instrument_id", "date"])
    if dup_rows.any():
        raise ValueError(f"{dup_rows.sum()} rows repeat (instrument_id, date)")

    return with_id
