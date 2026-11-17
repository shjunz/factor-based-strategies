'''
paths.py - 

'''

# %%
# Imports

import os
import re
from datetime import date
from pathlib import Path

# %%
# Data Directory

# Root of the data folder: <repo>/data (paths.py is at src/fbs/etl/)
DATA_DIR = Path(__file__).resolve().parents[3] / "data"

# Data layers
BRONZE_DIR = DATA_DIR / "bronze"
SILVER_DIR = DATA_DIR / "silver"
GOLD_DIR = DATA_DIR / "gold"

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
        Asset class code.
    category : str
        Instrument type.
    frequency : str
        Data frequency.

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
        return ",".join(values)
    return _scalar(value)

# Extraction file path
def extraction_path(source, product, dataset, filters, download_date, suffix,
                    columns=None):
    """
    Raw data file in the bronze layer, at
    bronze/{source}_{product}/{dataset}/{download_date}_{filters}{suffix}, so a
    dataset's files sort by download date.

    Filters are written as column=value joined by _, sorted by column, with
    dates as YYYYMMDD, a range as start-end (either side may be empty) and a
    list joined by commas. Selected columns are written the same way under the
    key columns. A download of the whole dataset is named ALL. The full filters
    are kept in the .json written next to the file by download_table.

    Parameters
    ----------
    source : str
        Data source, such as Sharadar.
    product : str
        Product of the source in snake case, such as fund_prices. A dataset
        shared by several products is saved under the product it was downloaded
        for.
    dataset : str
        Dataset of the product, such as SFP.
    filters : dict
        Column filters the data was downloaded with, as passed to
        download_table; empty for the whole dataset.
    download_date : datetime.date
        Download date.
    suffix : str
        File extension as returned by the data source, such as .zip.
    columns : list of str, optional
        Columns selected for the download; None for all columns.

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
    ...                 ".zip").name
    '20261101_ALL.zip'
    """

    # Name the file by its filters and columns and place it under
    # bronze/{source}_{product}/{dataset}/
    named = dict(filters) if columns is None else dict(filters, columns=columns)
    tokens = [f"{col}={_filter_token(named[col])}" for col in sorted(named)]
    name = f"{download_date:%Y%m%d}_{'_'.join(tokens) or 'ALL'}{suffix}"
    path = BRONZE_DIR / f"{source.lower()}_{product}" / dataset / name

    return path

# %%
# Clean Path

# Clean data file path
def clean_path(asset_class, category, frequency, source, dataset, clean_date):
    """
    Clean data file in the gold layer, at
    gold/{asset}/{category}/{frequency}/{source}_{dataset}_{clean_date}.parquet,
    so a dataset's files sort by clean date.

    Parameters
    ----------
    asset_class : str
        Asset class code: EQ, FI, FX or CM.
    category : str
        Instrument type: spot or derivative.
    frequency : str
        Data frequency, such as daily.
    source : str
        Data source, such as Sharadar.
    dataset : str
        Dataset of the data source, such as SEP.
    clean_date : datetime.date
        Clean date.

    Returns
    -------
    path : Path
        Absolute path of the clean data file.

    Examples
    --------
    >>> clean_path("EQ", "spot", "daily", "Sharadar", "SEP", date(2026, 11, 16)).name
    'sharadar_SEP_20261116.parquet'
    """

    # Name the file by source, dataset and clean date under the category directory
    name = f"{source.lower()}_{dataset}_{clean_date:%Y%m%d}.parquet"
    path = GOLD_DIR / category_dir(asset_class, category, frequency) / name

    return path
