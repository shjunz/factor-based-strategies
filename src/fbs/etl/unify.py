'''
unify.py - Unify raw data into the standard format.
'''

# %%
# Imports
from pathlib import Path
import exchange_calendars as xcals
import pandas as pd

# %%
# Standard fields of each asset class
STANDARD_FIELDS = {
    "EQ": ["instrument_id", "timestamp", "open", "high", "low", "close",
           "close_raw", "close_adj", "volume"],
}

# %%
# Field Names

# Field name mapping table of a data provider: src/fbs/etl/{provider}/metadata/field_map.csv
def field_map_path(provider):
    return Path(__file__).parent / provider.lower() / "metadata" / "field_map.csv"

# Field renaming
def rename_fields(raw, provider, dataset):
    """
    Rename raw fields to standard field names.

    Parameters
    ----------
    raw : pd.DataFrame
        Raw data of one dataset from one data provider. Index = row number,
        Columns = source field names.
    provider : str
        Data provider of `raw`, e.g. 'sharadar' (case-insensitive).
    dataset : str
        Dataset name of `raw`.

    Returns
    -------
    renamed : pd.DataFrame
        Raw data with standard field names. Index = row number, Columns =
        standard names for mapped fields, source names for the rest.
    """

    # Look up the standard names of this dataset's fields in field_map
    field_map = pd.read_csv(field_map_path(provider))
    rows = (field_map["provider"] == provider.lower()) & (field_map["dataset"] == dataset)
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
