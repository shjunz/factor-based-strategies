'''
paths.py

'''

# %%
# Imports

from pathlib import Path

# %%
# Data Directory

# Root of the data folder, two levels above etl/storage/
DATA_DIR = Path(__file__).resolve().parents[2] / "data"

# %%
# Category Directory

# Category directory
def category_dir(asset_class, category, frequency):
    """
    Category directory {asset_class}/{category}/{frequency}, shared by all data
    layers.

    Parameters
    ----------
    asset_class : str
        Asset class code: EQ, FI, FX or CM.
    category : str
        Instrument type: spot or derivative.
    frequency : str
        Data frequency: tick, second, minute, hour or daily.

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

# Extraction file path
def extraction_path(source, interface, source_code, download_date, asset_class,
                    category, frequency, suffix):
    """
    Raw data file in the extraction layer, named
    {source}_{interface}_{source_code}_{download_date}.

    Parameters
    ----------
    source : str
        Data source, such as Sharadar.
    interface : str
        Data interface or table, such as SEP.
    source_code : str
        Instrument code in the data source, or ALL for a whole table.
    download_date : datetime.date
        Download date.
    asset_class : str
        Asset class code: EQ, FI, FX or CM.
    category : str
        Instrument type: spot or derivative.
    frequency : str
        Data frequency: tick, second, minute, hour or daily.
    suffix : str
        File extension as returned by the data source, such as .zip.

    Returns
    -------
    path : Path
        Absolute path of the raw data file.
    """

    # Build the file name and place it under extraction/{category}/
    name = f"{source}_{interface}_{source_code}_{download_date:%Y%m%d}{suffix}"
    path = DATA_DIR / "extraction" / category_dir(asset_class, category, frequency) / name

    return path
