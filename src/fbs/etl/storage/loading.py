'''
loading.py - Write clean data files to the gold layer.
'''

# %%
# Clean Data Write

# Clean data write
def write_clean(clean, path):
    """
    Clean data written as a Parquet file, with rows sorted by instrument_id and
    timestamp.

    Parameters
    ----------
    clean : pd.DataFrame
        Clean data with instrument_id and timestamp columns.
    path : Path
        Destination Parquet file.

    Returns
    -------
    Path
        The written file.
    """

    # Create the parent directories if they don't exist
    path.parent.mkdir(parents=True, exist_ok=True)

    # Sort the rows and write them to a temporary file, then move it into place
    clean = clean.sort_values(["instrument_id", "timestamp"], ignore_index=True)
    tmp = path.with_name(path.name + ".part")
    clean.to_parquet(tmp, index=False)
    tmp.replace(path)

    return path
