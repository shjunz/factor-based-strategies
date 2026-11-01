'''
paths.py

'''

# %%
# Imports

import hashlib
import os
import re
from datetime import date
from pathlib import Path

# %%
# Data Directory

# Root of the data folder: <repo>/data (paths.py is at src/fbs/etl/storage/)
DATA_DIR = Path(__file__).resolve().parents[4] / "data"

# Data layers: raw extraction (M1.1), intermediate transforms (M1.2), clean data (M1.3)
BRONZE_DIR = DATA_DIR / "bronze"
SILVER_DIR = DATA_DIR / "silver"
GOLD_DIR = DATA_DIR / "gold"

# Small committed samples of every product's tables, kept apart from downloads
SAMPLE_DIR = BRONZE_DIR / "sample"

# Filter values beyond this count are written as a count and a short hash
MAX_FILTER_VALUES = 5

# %%
# Category Directory

# Category directory
def category_dir(asset_class, category, frequency):
    """
    Category directory {asset_class}/{category}/{frequency}, used by the gold
    layer.

    Parameters
    ----------
    asset_class : str
        Asset class code: EQ, FI, FX or CM.
    category : str
        Instrument type: spot or derivative.
    frequency : str
        Data frequency: tick, second, minute, hour or daily, or snapshot or
        event for data without a time grid.

    Returns
    -------
    cat_dir : Path
        Relative category directory.
    """

    # Join the three levels
    cat_dir = Path(asset_class) / category / frequency

    return cat_dir

# %%
# Extraction Path

# File-name text of a single filter value: dates as YYYYMMDD, no path separators
# or spaces
def _scalar(value):
    if isinstance(value, date):
        return f"{value:%Y%m%d}"
    text = str(value)
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return text.replace("-", "")
    return re.sub(r"[/\\\s]+", "-", text)

# File-name text of a filter: a range as start-end, a list joined by commas
def _filter_token(value):
    if isinstance(value, dict):
        if set(value) <= {"gte", "lte"}:
            return f"{_scalar(value.get('gte', ''))}-{_scalar(value.get('lte', ''))}"
        return ",".join(f"{op}{_scalar(v)}" for op, v in sorted(value.items()))
    if isinstance(value, (list, tuple)):
        values = sorted(_scalar(v) for v in value)
        if len(values) > MAX_FILTER_VALUES:
            digest = hashlib.sha1(",".join(values).encode()).hexdigest()[:7]
            return f"{len(values)}items-{digest}"
        return ",".join(values)
    return _scalar(value)

# Extraction file path
def extraction_path(source, product, table, filters, download_date, suffix,
                    columns=None, limit=None):
    """
    Raw data file in the bronze layer, at
    bronze/{source}_{product}/{table}/{download_date}_{filters}{suffix}, so a
    table's files sort by download date.

    Filters are written as column=value joined by _, sorted by column, with
    dates as YYYYMMDD, a range as start-end (either side may be empty) and a
    list joined by commas; a list longer than MAX_FILTER_VALUES is written as
    {count}items-{hash}. Selected columns are written the same way under the
    key columns, and a row limit as limit=N. A download of the whole table is
    named ALL. The full filters
    are kept in the .json written next to the file by download_table.

    Parameters
    ----------
    source : str
        Data source, such as Sharadar.
    product : str
        Product of the source in snake case, such as fund_prices. A table shared
        by several products is saved under the product it was downloaded for.
    table : str
        Table of the product, such as SFP.
    filters : dict
        Column filters the data was downloaded with, as passed to
        download_table; empty for the whole table.
    download_date : datetime.date
        Download date.
    suffix : str
        File extension as returned by the data source, such as .zip.
    columns : list of str, optional
        Columns selected for the download; None for all columns.
    limit : int, optional
        Maximum number of rows; None for no limit.

    Returns
    -------
    path : Path
        Absolute path of the raw data file.

    Examples
    --------
    >>> extraction_path("Sharadar", "fund_prices", "SFP",
    ...                 {"ticker": ["SPY", "QQQ"], "date": {"gte": "2024-01-01"}},
    ...                 date(2026, 11, 1), ".zip").name
    '20261101_date=20240101-_ticker=QQQ,SPY.zip'
    >>> extraction_path("Sharadar", "fund_prices", "SFP", {"ticker": "SPY"},
    ...                 date(2026, 11, 1), ".zip", columns=["date", "close"]).name
    '20261101_columns=close,date_ticker=SPY.zip'
    >>> extraction_path("Sharadar", "fund_prices", "SFP", {}, date(2026, 11, 1),
    ...                 ".zip", limit=500).name
    '20261101_limit=500.zip'
    """

    # Name the file by its filters, columns and limit and place it under
    # bronze/{source}_{product}/{table}/
    options = {"columns": columns, "limit": limit}
    named = dict(filters, **{k: v for k, v in options.items() if v is not None})
    tokens = [f"{col}={_filter_token(named[col])}" for col in sorted(named)]
    name = f"{download_date:%Y%m%d}_{'_'.join(tokens) or 'ALL'}{suffix}"
    path = BRONZE_DIR / f"{source.lower()}_{product}" / table / name

    return path
