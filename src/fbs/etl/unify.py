'''
unify.py - Unify raw data into the standard format.
'''

# %%
# Imports

import exchange_calendars as xcals
import pandas as pd

from fbs.etl.paths import DATA_DIR

# %%
# Standard Columns

# Standard columns of each asset class, in stored order
STANDARD_COLUMNS = {
    "EQ": ["instrument_id", "timestamp", "open", "high", "low", "close",
           "close_raw", "close_adj", "volume"],
}

# %%
# Column Names

# Standard column name mapping table
FIELD_MAP = DATA_DIR / "dictionary" / "field_map.csv"

# Column renaming
def rename_fields(raw, source, dataset):
    """
    Raw data with source column names replaced by standard column names.

    Parameters
    ----------
    raw : pd.DataFrame
        Raw data of one dataset from one data source.
    source : str
        Data source name, as registered in data/data_library.md.
    dataset : str
        Dataset name in the data source, such as SEP.

    Returns
    -------
    renamed : pd.DataFrame
        Raw data with standard column names. Columns not in the mapping table
        keep their source names.
    """

    # Source column to standard column for this data source and dataset
    field_map = pd.read_csv(FIELD_MAP)
    rows = (field_map["source"] == source) & (field_map["dataset"] == dataset)
    mapping = field_map.loc[rows].set_index("source_field")["field"]

    # Rename the mapped columns
    renamed = raw.rename(columns=mapping.to_dict())

    return renamed

# %%
# Time

# Session close times
def close_times(dates, calendar):
    """
    UTC close times of the exchange sessions on the given dates, including
    daylight saving time and early closes.

    Parameters
    ----------
    dates : pd.Series
        Session dates, without time of day.
    calendar : str
        Exchange calendar code in exchange_calendars, such as XNYS.

    Returns
    -------
    closes : pd.Series
        UTC close time of each date, aligned with dates.

    Raises
    ------
    ValueError
        If a date is not a session of the calendar.
    """

    # Close time of every session from the first to the last date
    cal = xcals.get_calendar(calendar, start=dates.min(), end=dates.max())

    # Close time of each date
    closes = dates.map(cal.closes)
    missing = closes.isna() & dates.notna()
    if missing.any():
        raise ValueError(f"{missing.sum()} rows fall on dates that are not "
                         f"{calendar} sessions: "
                         f"{dates[missing].dt.strftime('%Y-%m-%d').unique()[:10].tolist()}")

    return closes
