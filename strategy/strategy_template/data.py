"""Download this strategy's data from Sharadar SEP and return it in the shape weights.compute expects.

Contract: fetch(config, start, end) -> DataFrame
    index   = session dates (DatetimeIndex, tz-naive, ascending), cut to [start, end]
    columns = one column of config data.field per symbol in config universe
For paper trading the runner calls fetch with end = signal session; if Sharadar has not yet
published that session, the last row is earlier and the runner blocks the run as stale data.

Steps, following research_spec.md M1 (all files under ./data/, never committed):
    1. extract  SHARADAR/SEP for the universe and [start, end], and SHARADAR/TICKERS for the
                FIGIs, saved as raw files in data/bronze/sharadar_equity_prices/{table}/
    2. clean    standard column names (data/dictionary/field_map.csv), timestamp = UTC session
                close, instrument_id = composite FIGI; saved to
                data/gold/EQ/spot/daily/sharadar_SEP_{clean_date}.parquet
    3. shape    pivot config data.field to one column per symbol
Needs NASDAQ_DATA_LINK_API_KEY in the environment or in the repo-root .env.
Keep fetch's name and signature; change only what the strategy needs (e.g. another field).
"""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

import nasdaqdatalink
import pandas as pd
from dotenv import load_dotenv

from fbs.etl.extract.sharadar import download_table, read_table
from fbs.etl.storage.paths import BRONZE_DIR, category_dir, extraction_path
from fbs.etl.transform.unify import rename_fields

DATA_DIR = Path(__file__).parent / "data"
REPO_ROOT = Path(__file__).resolve().parents[2]
PRODUCT = "equity_prices"          # Sharadar product that holds SEP and its TICKERS rows
EXCHANGE_TZ = "America/New_York"
CLOSE_TIME = pd.Timedelta(hours=16)
FIELDS = ["open", "high", "low", "close", "close_raw", "close_adj", "volume"]


def _extract(table: str, filters: dict, columns: list[str]) -> pd.DataFrame:
    """Download one Sharadar table into this strategy's bronze folder and read it back."""
    repo_path = extraction_path("Sharadar", PRODUCT, table, filters, date.today(), ".zip",
                                columns=columns)
    path = DATA_DIR / "bronze" / repo_path.relative_to(BRONZE_DIR)
    download_table(table, path, method="get", columns=columns, overwrite=True, **filters)
    return read_table(path)


def _figi_map(symbols: list[str]) -> pd.Series:
    """ticker -> composite FIGI from TICKERS (rows of table SEP; listed rows win over delisted)."""
    tickers = _extract("TICKERS", {"table": "SEP", "ticker": symbols},
                       ["ticker", "figi", "isdelisted", "lastupdated"])
    tickers = tickers.dropna(subset=["figi"]).sort_values(["isdelisted", "lastupdated"],
                                                          ascending=[True, False])
    figi = tickers.drop_duplicates("ticker").set_index("ticker")["figi"]
    missing = sorted(set(symbols) - set(figi.index))
    if missing:
        raise KeyError(f"Sharadar TICKERS has no FIGI for {missing}")
    return figi


def _to_gold(sep: pd.DataFrame, figi: pd.Series) -> pd.DataFrame:
    """Raw SEP rows -> gold format (M1.2): standard columns, UTC close timestamp, instrument_id."""
    gold = rename_fields(sep, "Sharadar")
    session_close = (pd.to_datetime(gold["timestamp"]) + CLOSE_TIME).dt.tz_localize(EXCHANGE_TZ)
    gold["timestamp"] = session_close.dt.tz_convert("UTC")
    gold["instrument_id"] = gold["ticker"].map(figi).astype("string")
    gold = gold[["timestamp", "instrument_id", *FIELDS]]
    return gold.sort_values(["timestamp", "instrument_id"], ignore_index=True)


def _save_gold(gold: pd.DataFrame, figi: pd.Series) -> Path:
    """Write the gold file (M1.3) and the ticker -> instrument_id map next to the gold root."""
    gold_dir = DATA_DIR / "gold"
    path = gold_dir / category_dir("EQ", "spot", "daily") / f"sharadar_SEP_{date.today():%Y%m%d}.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    gold.to_parquet(path, index=False)
    (pd.DataFrame({"source": "sharadar", "source_id": figi.index, "instrument_id": figi.values})
       .to_csv(gold_dir / "instrument_map.csv", index=False))
    return path


def _set_api_key() -> None:
    # nasdaqdatalink reads the variable once at import, possibly before .env was loaded
    load_dotenv(REPO_ROOT / ".env")
    key = os.environ.get("NASDAQ_DATA_LINK_API_KEY")
    if not key:
        raise RuntimeError("set NASDAQ_DATA_LINK_API_KEY in the environment or the repo-root .env")
    nasdaqdatalink.ApiConfig.api_key = key


def fetch(config: dict, start: date, end: date) -> pd.DataFrame:
    _set_api_key()
    universe = list(config["universe"])
    field = config["data"].get("field", "close_adj")
    if field not in FIELDS:
        raise ValueError(f"data.field must be one of {FIELDS}, got {field!r}")

    date_range = {"gte": pd.Timestamp(start).date().isoformat(),
                  "lte": pd.Timestamp(end).date().isoformat()}
    sep = _extract("SEP", {"ticker": universe, "date": date_range}, None)
    if sep.empty:
        raise ValueError(f"Sharadar SEP returned no rows for {start} to {end}")
    figi = _figi_map(universe)
    gold = _to_gold(sep, figi)
    _save_gold(gold, figi)

    # Gold -> one column per symbol, dated by the exchange session
    to_symbol = pd.Series(figi.index, index=figi.values)
    sessions = gold["timestamp"].dt.tz_convert(EXCHANGE_TZ).dt.tz_localize(None).dt.normalize()
    wide = (gold.assign(date=sessions, symbol=gold["instrument_id"].map(to_symbol))
                .pivot(index="date", columns="symbol", values=field)
                .reindex(columns=universe))
    wide.columns.name = None
    return wide.loc[pd.Timestamp(start):pd.Timestamp(end)]
