'''
pipeline.py - ETL flow from raw data to clean data.
'''

# %%
# Imports

from datetime import date

from fbs.etl.extract.sharadar import read_table
from fbs.etl.storage.loading import write_clean
from fbs.etl.storage.paths import BRONZE_DIR, clean_path
from fbs.etl.transform.identifiers import add_instrument_id
from fbs.etl.transform.unify import STANDARD_COLUMNS, close_times, rename_fields

# %%
# Sharadar SEP

# Sharadar SEP clean
def clean_sharadar_sep(sep_path, tickers_path, clean_date=None):
    """
    Clean Sharadar SEP daily prices written to the gold layer at
    EQ/spot/daily/sharadar_SEP_{clean_date}.parquet.

    Parameters
    ----------
    sep_path : Path
        Downloaded SEP zip file.
    tickers_path : Path
        Downloaded TICKERS zip file.
    clean_date : datetime.date
        Clean date in the file name. Today if None.

    Returns
    -------
    Path
        The written clean data file.
    """

    # Raw SEP prices and the TICKERS columns needed for identifiers
    sep = read_table(sep_path)
    tickers = read_table(tickers_path, columns=["table", "ticker", "permaticker"])

    # M1.2.1 Identifiers: permaticker as instrument_id
    sep = add_instrument_id(sep, tickers, "SEP")

    # Format: standard column names, NYSE close time in UTC, standard columns
    sep = rename_fields(sep, "Sharadar", "SEP")
    sep["timestamp"] = close_times(sep["timestamp"], "XNYS")
    clean = sep[STANDARD_COLUMNS["EQ"]]

    # Parquet file in the gold layer
    path = clean_path("EQ", "spot", "daily", "Sharadar", "SEP",
                      clean_date or date.today())
    write_clean(clean, path)

    return path

# %%
# Run

if __name__ == "__main__":
    prices = BRONZE_DIR / "sharadar_equity_prices"
    print(clean_sharadar_sep(prices / "SEP" / "20261029_ALL.zip",
                             prices / "TICKERS" / "20261029_ALL.zip"))
