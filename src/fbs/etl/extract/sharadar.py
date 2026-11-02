'''
sharadar.py - Download data from Sharadar tables on Nasdaq Data Link.
'''

# %%
# Imports

import json
import warnings
from datetime import datetime, timezone

import nasdaqdatalink

# %%
# Constants

# Rows per page returned by get_table
PAGE_SIZE = 10_000

# Candidate sort keys, applied in this order when present (API data is unsorted)
SORT_KEYS = ["ticker", "dimension", "calendardate", "datekey", "date"]

# %%
# Table Download

# Sharadar table download
def download_table(table, path, /, method="export", limit=None, columns=None,
                   overwrite=False, **filters):
    """
    Sharadar table download from Nasdaq Data Link.

    Parameters
    ----------
    table : str
        Sharadar table name.
    path : Path
        Destination zip file (zipped CSV for both methods).
    method : {"export", "get"}
        "export": server-side bulk export (qopts.export), no row limit.
        "get": paged API query (get_table), up to about 1,000,000 rows.
    limit : int, optional
        Maximum number of rows, "get" only. All matching rows if None.
    columns : list of str, optional
        Columns to keep (qopts.columns). All columns if None.
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
        The written file. Its download parameters (table, filters, columns,
        method, limit, download time) are written next to it as a .json with
        the same name.
    """

    # Keep the parameters as passed, before the filters take the query options
    params = {"table": table, "filters": dict(filters), "columns": columns,
              "method": method, "limit": limit}

    # Check the arguments
    if method not in ("export", "get"):
        raise ValueError(f"method must be 'export' or 'get', got {method!r}")
    if limit is not None and method == "export":
        raise ValueError("limit is only supported with method='get'")

    # Stop if the file already exists
    if path.exists() and not overwrite:
        raise FileExistsError(path)

    # Create the parent directories if they don't exist
    path.parent.mkdir(parents=True, exist_ok=True)

    # Query options: selected columns, and a single page when it holds the limit
    qopts = filters.pop("qopts", {})
    if columns is not None:
        qopts["columns"] = list(columns)
    one_page = limit is not None and limit <= PAGE_SIZE
    if one_page:
        qopts["per_page"] = limit
    if qopts:
        filters["qopts"] = qopts

    # Write to a temporary file so an interrupted download leaves no partial file
    tmp = path.with_name(path.name + ".part")
    code = f"SHARADAR/{table}"

    # API key is read from the NASDAQ_DATA_LINK_API_KEY environment variable
    if method == "export":
        nasdaqdatalink.export_table(code, filename=str(tmp), **filters)
    else:
        with warnings.catch_warnings():
            # Stopping after one page triggers an expected truncation warning
            warnings.simplefilter("ignore", UserWarning)
            df = nasdaqdatalink.get_table(code, paginate=not one_page, **filters)

        # Keep the limit and sort on whichever keys the table has (API data is unsorted)
        df = df.iloc[:limit].sort_values([k for k in SORT_KEYS if k in df.columns],
                                         ignore_index=True)
        df.to_csv(tmp, index=False,
                  compression={"method": "zip", "archive_name": f"{path.stem}.csv"})

    tmp.replace(path)

    # Record the full parameters, since long filter values are hashed in the file name
    params["downloaded_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    path.with_suffix(".json").write_text(json.dumps(params, indent=2, default=str))

    return path
