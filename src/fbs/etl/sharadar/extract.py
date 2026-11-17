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
# Table Download

# Sharadar table download
def download_table(table, path, /, columns=None, overwrite=False, **filters):
    """
    Sharadar table download from Nasdaq Data Link as a bulk export
    (export_table), with its download parameters written next to it as a .json
    of the same name.

    Parameters
    ----------
    table : str
        Sharadar table name.
    path : Path
        Destination zip file.
    columns : list of str
        Columns to keep. All columns if None.
    overwrite : bool
        Replace an existing file instead of raising.
    **filters
        Optional Nasdaq Data Link filters on the table's columns,
        e.g. ticker=['AADR', 'BAB'] or date={'gte': '2017-01-01'}.
        table and path are positional-only, so a column named "table"
        (TICKERS, INDICATORS) can be filtered as table='SFP'.

    Returns
    -------
    Path
        The written file.
    """

    # Keep the parameters as passed, before the filters take the query options
    params = {"table": table, "filters": dict(filters), "columns": columns}

    # Stop if the file already exists
    if path.exists() and not overwrite:
        raise FileExistsError(path)

    # Create the parent directories if they don't exist
    path.parent.mkdir(parents=True, exist_ok=True)

    # Query options: selected columns
    qopts = filters.pop("qopts", {})
    if columns is not None:
        qopts["columns"] = list(columns)
    if qopts:
        filters["qopts"] = qopts

    # Write to a temporary file so an interrupted download leaves no partial file
    tmp = path.with_name(path.name + ".part")

    # API key is read from the NASDAQ_DATA_LINK_API_KEY environment variable
    nasdaqdatalink.export_table(f"SHARADAR/{table}", filename=str(tmp), **filters)

    tmp.replace(path)

    # Record the full download parameters in a .json next to the file
    params["downloaded_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    path.with_suffix(".json").write_text(json.dumps(params, indent=2, default=str))

    return path

# %%
# Table Read

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
        Table with its date columns parsed as dates and its rows sorted by
        SORT_KEYS. Only empty fields are read as missing, so text such as the
        ticker "NA" is kept as is.
    """

    # Date columns among the columns to read
    names = pd.read_csv(path, nrows=0).columns if columns is None else columns
    dates = [c for c in DATE_COLUMNS if c in names]

    # Read the zipped CSV, with empty fields as the only missing values
    table = pd.read_csv(path, usecols=columns, parse_dates=dates,
                        keep_default_na=False, na_values=[""])

    # Sort on whichever keys the table has (downloaded rows are unsorted)
    table = table.sort_values([k for k in SORT_KEYS if k in table.columns],
                              ignore_index=True)

    return table