'''
unify.py - Unify raw data into the standard format.
'''

# %%
# Imports
from pathlib import Path
import exchange_calendars as xcals
from exchange_calendars.errors import NoSessionsError
import pandas as pd

# %%
# Standard fields of each asset class
STANDARD_FIELDS = {
    "EQ": ["instrument_id", "timestamp", "open", "high", "low", "close",
           "close_raw", "close_adj", "volume"],
}

# %%
# Field Names

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

    Examples
    --------
    >>> raw = pd.DataFrame({"ticker": ["AAPL"], "date": ["2024-01-02"],
    ...                     "closeadj": [184.0], "closeunadj": [185.6]})
    >>> rename_fields(raw, "Sharadar", "SEP").columns.tolist()
    ['ticker', 'timestamp', 'close_adj', 'close_raw']
    """

    # Look up the standard names of this dataset's fields in the provider's
    # field map, src/fbs/etl/provider/{provider}/metadata/field_map.csv
    field_map = pd.read_csv(Path(__file__).parent / "provider" / provider.lower() / "metadata" / "field_map.csv")
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

    Examples
    --------
    >>> dates = pd.Series(pd.to_datetime(["2024-01-02", "2024-07-03", "2024-11-29"]))
    >>> map_date_timestamps(dates, "XNYS")
    0   2024-01-02 21:00:00+00:00
    1   2024-07-03 17:00:00+00:00
    2   2024-11-29 18:00:00+00:00
    dtype: datetime64[ns, UTC]
    >>> map_date_timestamps(pd.Series(pd.to_datetime(["2024-01-05", "2024-01-06"])),
    ...                     "XNYS")
    Traceback (most recent call last):
    ...
    ValueError: dates not XNYS sessions: ['2024-01-06']
    >>> map_date_timestamps(pd.Series(pd.to_datetime(["2024-01-06", "2024-01-07"])),
    ...                     "XNYS")
    Traceback (most recent call last):
    ...
    ValueError: dates not XNYS sessions: ['2024-01-06', '2024-01-07']
    """

    # Get close timestamps of all sessions from the first date to one day after
    # the last, since the calendar needs its start before its end, and map each
    # date to its close timestamp
    try:
        cal = xcals.get_calendar(calendar, start=dates.min(),
                                 end=dates.max() + pd.Timedelta(days=1))
        timestamps = dates.map(cal.closes)

    # No session in the range at all (e.g. only weekend dates), so no date is a
    # session and every date is reported below
    except NoSessionsError:
        timestamps = pd.Series(pd.NaT, index=dates.index, dtype="datetime64[ns, UTC]")

    # Check every date is a session
    missing = timestamps.isna() & dates.notna()
    if missing.any():
        raise ValueError(f"dates not {calendar} sessions: {dates[missing].dt.strftime('%Y-%m-%d').unique().tolist()}")

    return timestamps
