'''
sharadar.py - Download data from Sharadar tables on Nasdaq Data Link.
'''

# %%
# Imports

import nasdaqdatalink

# %%
# Table Download

# Sharadar table download
def download_table(table, path, **filters):
    """
    Sharadar table bulk download from Nasdaq Data Link.

    Parameters
    ----------
    table : str
        Sharadar table name.
    path : Path
        Destination of the downloaded zip file.
    **filters
        Optional Nasdaq Data Link filters on the table's columns.
    """

    # Stop if the file already exists
    if path.exists():
        raise FileExistsError(path)

    # Create the parent directories if they don't exist
    path.parent.mkdir(parents=True, exist_ok=True)

    # API key is read from the NASDAQ_DATA_LINK_API_KEY environment variable
    nasdaqdatalink.export_table(f"SHARADAR/{table}", filename=str(path), **filters)