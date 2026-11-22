'''
extract.py - Download and read data from Sharadar products on Nasdaq Data Link.
'''

# %%
# Imports
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import nasdaqdatalink
import pandas as pd
import yaml

# %%
# Constants

# Provider settings: API code and the name of the API key variable (no secrets)
PROVIDER_PATH = Path(__file__).parent / "metadata" / "provider.yaml"

# Columns to sort rows by in priority order, if present in the table
SORT_KEYS = ["ticker", "dimension", "calendardate", "datekey", "date"]

# Columns parsed as dates, if present in the table
DATE_COLUMNS = ["date", "datekey", "calendardate", "reportperiod", "lastupdated",
                "firstadded", "firstpricedate", "lastpricedate", "firstquarter",
                "lastquarter"]

# %%
# Provider settings
def provider_config():
    """
    Sharadar provider settings from metadata/provider.yaml.

    Returns
    -------
    config : dict
        provider, vendor, api, api_key_env, extractor. api_key_env is the
        name of the API key environment variable, not the key.
    """

    with open(PROVIDER_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)

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

    # API code and key variable name come from metadata/provider.yaml; the key
    # itself comes from that environment variable (.env locally, Secrets
    # Manager on ECS). Set it here because nasdaqdatalink reads the variable
    # only once at import, possibly before .env was loaded.
    config = provider_config()
    key = os.environ.get(config["api_key_env"])
    if key:
        nasdaqdatalink.ApiConfig.api_key = key
    elif not nasdaqdatalink.ApiConfig.api_key:
        raise RuntimeError(f"set the {config['api_key_env']} environment variable "
                           "(.env locally, Secrets Manager on ECS)")
    nasdaqdatalink.export_table(config["api"].format(dataset=table),
                                filename=str(tmp), **query)

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