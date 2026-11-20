'''
identifiers.py - Instrument IDs in Sharadar data.
'''

# %%
# Imports
import pandas as pd

# %%
# Sharadar instrument ID
def add_instrument_id(raw, tickers, table):
    """
    Add instrument IDs to Sharadar raw data by permaticker.

    Parameters
    ----------
    raw : pd.DataFrame
        Raw data of a Sharadar table. Index = row number, Columns = ticker,
        date, table's other columns.
    tickers : pd.DataFrame
        Sharadar TICKERS table. Index = row number, Columns = table, ticker,
        permaticker.
    table : str
        Sharadar table name of `raw`.

    Returns
    -------
    with_id : pd.DataFrame
        Raw data with instrument IDs. Index = row number, Columns = raw columns,
        instrument_id.

    Raises
    ------
    ValueError
        If a ticker maps to more than one permaticker in TICKERS for the table.
        If a permaticker maps to more than one ticker in TICKERS for the table.
        If a row has no instrument_id.
    """

    # Find tickers and permaticker pairs for this table
    which_table = tickers["table"] == table
    ids = tickers.loc[which_table, ["ticker", "permaticker"]].drop_duplicates()

    # Check for one to one
    dup_tickers = ids.loc[ids["ticker"].duplicated(), "ticker"]
    if not dup_tickers.empty:
        raise ValueError(f"tickers with more than one permaticker: {dup_tickers.tolist()}")
    dup_ids = ids.loc[ids["permaticker"].duplicated(), "permaticker"]
    if not dup_ids.empty:
        raise ValueError(f"permatickers with more than one ticker: {dup_ids.tolist()}")

    # instrument_id = permaticker merge with raw data on ticker
    ids = ids.rename(columns={"permaticker": "instrument_id"})
    with_id = raw.merge(ids, on="ticker", how="left")

    # Check every row has an instrument_id
    missing = with_id["instrument_id"].isna()
    if missing.any():
        raise ValueError(f"tickers not in TICKERS: {with_id.loc[missing, 'ticker'].unique().tolist()}")

    return with_id