'''
unify.py - Unify raw data into the standard format.
'''

# %%
# Imports
import exchange_calendars as xcals
import pandas as pd
from fbs.etl.paths import DATA_DIR

# %%
# Standard fields of each asset class
STANDARD_FIELDS = {
    "EQ": ["instrument_id", "timestamp", "open", "high", "low", "close",
           "close_raw", "close_adj", "volume"],
}

# %%
# Field Names

# Field name mapping table
FIELD_MAP = DATA_DIR / "dictionary" / "field_map.csv"

# Field renaming
def rename_fields(raw, source, dataset):
    """
    Rename raw fields to standard field names.

    Parameters
    ----------
    raw : pd.DataFrame
        Raw data of one dataset from one data source. Index = row number,
        Columns = source field names.
    source : str
        Source name of `raw`.
    dataset : str
        Dataset name of `raw`.

    Returns
    -------
    renamed : pd.DataFrame
        Raw data with standard field names. Index = row number, Columns =
        standard names for mapped fields, source names for the rest.
    """

    # Look up the standard names of this dataset's fields in field_map
    field_map = pd.read_csv(FIELD_MAP)
    rows = (field_map["source"] == source) & (field_map["dataset"] == dataset)
    mapping = field_map.loc[rows].set_index("source_field")["field"]

    # Rename the mapped fields
    renamed = raw.rename(columns=mapping)

    return renamed

# %%
# Close timestamps of dates
def map_date_timestamps(dates, calendar):
    """
    Map dates to UTC close timestamps.

    Parameters
    ----------
    dates : pd.Series
        Date per row.
    calendar : str
        Exchange calendar code in exchange_calendars.

    Returns
    -------
    timestamps : pd.Series
        UTC close timestamp per row.

    Raises
    ------
    ValueError
        If a date is not a session of the calendar.
    """

    # Get close timestamps of all sessions from the first date to one day after
    # the last, since the calendar needs its start before its end
    cal = xcals.get_calendar(calendar, start=dates.min(),
                             end=dates.max() + pd.Timedelta(days=1))

    # Map each date to its close timestamp
    timestamps = dates.map(cal.closes)

    # Check every date is a session
    missing = timestamps.isna() & dates.notna()
    if missing.any():
        raise ValueError(f"dates not {calendar} sessions: {dates[missing].dt.strftime('%Y-%m-%d').unique().tolist()}")

    return timestamps
