'''
extract.py - Download and read data from Sharadar products on Nasdaq Data Link.
'''

# %%
# Imports
import json
from datetime import datetime, timezone
import nasdaqdatalink
import pandas as pd

# %%
# Constants

# Columns to sort rows by in priority order, if present in the table
SORT_KEYS = ["ticker", "dimension", "calendardate", "datekey", "date"]

# Columns parsed as dates, if present in the table
DATE_COLUMNS = ["date", "datekey", "calendardate", "reportperiod", "lastupdated",
                "firstadded", "firstpricedate", "lastpricedate", "firstquarter",
                "lastquarter"]

# %%
# Sharadar table download
def download_table(table, path, /, columns=None, overwrite=False, **filters):
    """
    Sharadar table download from Nasdaq Data Link, with a .json record.

    Parameters
    ----------
    table : str
        Sharadar table name.
    path : Path
        Destination zip file.
    columns : list of str
        Columns selected for the download. All columns if None.
    overwrite : bool
        True to replace an existing file at `path`.
    **filters
        Row filters for the download, e.g. ticker=['AADR', 'BAB'] or
        date={'gte': '2017-01-01'}.
        A filter on the column named "table" (in TICKERS, INDICATORS) is
        passed as table='SFP'; table and path are positional-only for this.

    Returns
    -------
    path : Path
        Destination zip file.

    Raises
    ------
    FileExistsError
        If `path` exists and `overwrite` is False.
    """

    # Stop if the file already exists
    if path.exists() and not overwrite:
        raise FileExistsError(path)

    # Create the parent directories if they don't exist
    path.parent.mkdir(parents=True, exist_ok=True)

    # Build the query from the filters and the selected columns
    query = dict(filters)
    if columns is not None:
        query["qopts"] = {"columns": list(columns)}

    # Write to a temporary file so an interrupted download leaves no partial file
    tmp = path.with_name(path.name + ".part")

    # API key is read from the NASDAQ_DATA_LINK_API_KEY environment variable
    nasdaqdatalink.export_table(f"SHARADAR/{table}", filename=str(tmp), **query)

    tmp.replace(path)

    # Write the .json record
    record = {"table": table, "filters": filters, "columns": columns,
              "downloaded_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    record_path = path.with_suffix(".json")
    tmp = record_path.with_name(record_path.name + ".part")
    tmp.write_text(json.dumps(record, indent=2, default=str))
    tmp.replace(record_path)

    return path

# %%
# Sharadar table read
def read_table(path, columns=None):
    """
    Sharadar table read from a downloaded zip file.

    Parameters
    ----------
    path : Path
        Downloaded zip file.
    columns : list of str
        Columns to read. All columns if None.

    Returns
    -------
    table : pd.DataFrame
        Sharadar table with date columns parsed as dates and rows sorted by
        SORT_KEYS. Index = row number, Columns = the table's columns.
    """

    # Read the zipped CSV
    # Only empty fields as missing values
    table = pd.read_csv(path, usecols=columns, keep_default_na=False, na_values=[""])

    # Parse the date columns as dates
    for col in DATE_COLUMNS:
        if col in table.columns:
            table[col] = pd.to_datetime(table[col])

    # Sort on keys
    table = table.sort_values([k for k in SORT_KEYS if k in table.columns],
                              ignore_index=True)

    return table