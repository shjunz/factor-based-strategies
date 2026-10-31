'''
unify.py - Unify raw data into the standard format.
'''

# %%
# Imports

import pandas as pd

from etl.storage.paths import DATA_DIR

# %%
# Column Names

# Standard column name mapping table
FIELD_MAP = DATA_DIR / "dictionary" / "field_map.csv"

# Column renaming
def rename_fields(raw, source):
    """
    Raw data with source column names replaced by standard column names.

    Parameters
    ----------
    raw : pd.DataFrame
        Raw data from one data source.
    source : str
        Data source name, as registered in data/data_library.md.

    Returns
    -------
    renamed : pd.DataFrame
        Raw data with standard column names. Columns not in the mapping table
        keep their source names.
    """

    # Source column to standard column for this data source
    field_map = pd.read_csv(FIELD_MAP)
    mapping = field_map.loc[field_map["source"] == source].set_index("source_field")["field"]

    # Rename the mapped columns
    renamed = raw.rename(columns=mapping.to_dict())

    return renamed
