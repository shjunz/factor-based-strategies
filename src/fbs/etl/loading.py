'''
loading.py - Save clean data files.
'''

# %%
# Imports
import json
from fbs.etl.paths import DATA_DIR

# %%
# Save clean data files
def save_clean(clean, path, sources):
    """
    Clean data written as a Parquet file, with rows sorted by instrument_id and
    timestamp, and a .json record.

    Parameters
    ----------
    clean : pd.DataFrame
        Clean data. Index = row number, Columns = instrument_id, timestamp,
        other standard columns.
    path : Path
        Destination Parquet file.
    sources : list of Path
        Raw data files used to produce `clean`.

    Returns
    -------
    Path
        The written file.

    Raises
    ------
    ValueError
        If (instrument_id, timestamp) is not unique.
    """

    # Check that (instrument_id, timestamp) is unique
    dup_rows = clean.duplicated(["instrument_id", "timestamp"])
    if dup_rows.any():
        raise ValueError(f"{dup_rows.sum()} rows repeat (instrument_id, timestamp)")

    # Create the parent directories if they don't exist
    path.parent.mkdir(parents=True, exist_ok=True)

    # Sort the rows and write them to a temporary file, then move it into place
    clean = clean.sort_values(["instrument_id", "timestamp"], ignore_index=True)
    tmp = path.with_name(path.name + ".part")
    clean.to_parquet(tmp, index=False)
    tmp.replace(path)

    # Write the .json record
    meta = {"start": f"{clean['timestamp'].min():%Y-%m-%d}",
            "end": f"{clean['timestamp'].max():%Y-%m-%d}",
            "sources": [p.relative_to(DATA_DIR).as_posix() for p in sources]}
    meta_path = path.with_suffix(".json")
    tmp = meta_path.with_name(meta_path.name + ".part")
    tmp.write_text(json.dumps(meta, indent=2))
    tmp.replace(meta_path)

    return path
