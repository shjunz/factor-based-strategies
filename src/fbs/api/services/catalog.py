'''
catalog.py - Table schemas read from the latest Sharadar INDICATORS download,
downloading INDICATORS first when there is none.
'''

# %%
# Imports

import logging
import threading
from datetime import date

import pandas as pd

from fbs.etl.extract.sharadar import download_table
from fbs.etl.storage.paths import BRONZE_DIR, extraction_path

# %%
# Catalog

# Whole-table INDICATORS downloads of any product, named {download_date}_ALL.zip
INDICATORS_GLOB = "sharadar_*/INDICATORS/*_ALL.zip"

# Schemas by table, and the INDICATORS file they were read from
_cache = {"path": None, "schemas": {}}

# One automatic INDICATORS download at a time
_lock = threading.Lock()

# Latest INDICATORS download, downloading it when there is none (a fresh clone
# has no data); None if that download fails, for example without an API key
def indicators_file():
    with _lock:
        # Latest by download date, which starts the file name
        files = sorted(BRONZE_DIR.glob(INDICATORS_GLOB), key=lambda p: p.name)
        if files:
            return files[-1]

        path = extraction_path("Sharadar", "fund_prices", "INDICATORS", {},
                               date.today(), ".zip")
        try:
            download_table("INDICATORS", path, method="get")
        except Exception:
            logging.getLogger(__name__).exception("automatic INDICATORS download failed")
            return None
        return path

# Columns, filters, primary key and column types of a table, None if INDICATORS is not
# available or does not list the table
def table_schema(table):
    path = indicators_file()
    if path is None:
        return None

    # Re-read only when a newer INDICATORS download appears
    if _cache["path"] != path:
        df = pd.read_csv(path)
        _cache["schemas"] = {
            t: {"columns": g["indicator"].tolist(),
                "filters": g.loc[g["isfilter"] == "Y", "indicator"].tolist(),
                "keys": g.loc[g["isprimarykey"] == "Y", "indicator"].tolist(),
                # unittype by column, such as "date (YYYY-MM-DD)" or "USD/share";
                # "" where INDICATORS leaves it blank
                "types": dict(zip(g["indicator"], g["unittype"].fillna("")))}
            for t, g in df.groupby("table", sort=False)}
        _cache["path"] = path

    return _cache["schemas"].get(table)
