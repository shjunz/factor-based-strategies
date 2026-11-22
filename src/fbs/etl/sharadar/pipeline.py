'''
pipeline.py - ETL flow from raw data to clean data.
'''

# %%
# Imports
from datetime import datetime, timezone
from fbs.etl.sharadar.extract import read_table
from fbs.etl.loading import save_clean
from fbs.etl.paths import BRONZE_DIR, gold_path
from fbs.etl.sharadar.identifiers import add_instrument_id
from fbs.etl.unify import STANDARD_FIELDS, map_date_timestamps, rename_fields

# %%
# Clean SEP
def clean_sep(sep_path, tickers_path, clean_date=None):
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
        Clean date in the file name. Today in UTC if None.

    Returns
    -------
    path : Path
        The written clean data file.

    Examples
    --------
    Reads the bronze zip files and writes to the gold layer under data/:

    >>> prices = BRONZE_DIR / "sharadar_equity_prices"
    >>> clean_sep(prices / "SEP" / "20261029_ALL.zip",
    ...           prices / "TICKERS" / "20261029_ALL.zip",
    ...           clean_date=date(2026, 10, 29))  # doctest: +SKIP
    PosixPath('.../data/gold/EQ/spot/daily/sharadar_SEP_20261029.parquet')
    """

    # Raw SEP prices and the TICKERS columns needed for identifiers
    sep = read_table(sep_path)
    tickers = read_table(tickers_path, columns=["table", "ticker", "permaticker"])

    # Identifiers
    sep = add_instrument_id(sep, tickers, "SEP")

    # Format
    sep = rename_fields(sep, "sharadar", "SEP")
    sep["timestamp"] = map_date_timestamps(sep["timestamp"], "XNYS")
    clean = sep[STANDARD_FIELDS["EQ"]]

    # Parquet file at gold layer
    path = gold_path("EQ", "spot", "daily", "Sharadar", "SEP",
                     clean_date or datetime.now(timezone.utc).date())
    save_clean(clean, path, [sep_path, tickers_path])

    return path

# %%
# Run
if __name__ == "__main__":
    prices = BRONZE_DIR / "sharadar_equity_prices"
    print(clean_sep(prices / "SEP" / "20261029_ALL.zip",
                    prices / "TICKERS" / "20261029_ALL.zip"))
