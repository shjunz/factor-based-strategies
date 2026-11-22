'''
data.py - Prices of this strategy's universe from Sharadar SEP, in the shape
weights.compute expects, kept in a local store under ./data/ that each run
updates incrementally instead of downloading the full history again.

The runner calls fetch(config, start, end) with end = signal session. If
Sharadar has not published that session yet, the last row is earlier and the
runner blocks the run as stale data.

fetch follows research_spec.md M1; every file goes under ./data/ and is never
committed:
    1. Sync: download only what the local store lacks to data/bronze/sharadar_equity_prices/
        - a ticker never stored: its rows from start onward
        - a stored ticker whose rows begin after start: the missing earlier rows
        - every stored ticker: the rows Sharadar updated since the last sync
          (new sessions, and history revised by splits and dividends)
    2. Merge into the gold store data/gold/EQ/spot/daily/sharadar_SEP_{clean_date}.parquet,
       a downloaded row replacing the stored row of the same session and instrument;
       the sync state goes to data/sync_state.json. Every file carries the
       strategy (and gold the provider, dataset and clean_date) as columns,
       not only in its path, so the files join on them
    3. Pivot config data.field to one column per symbol, from start to end

Delete data/sync_state.json to download the full history again on the next run.

Needs NASDAQ_DATA_LINK_API_KEY in the environment or the repo-root .env.
'''

# %%
# Imports

import json
import os
from datetime import date, timedelta
from pathlib import Path

import nasdaqdatalink
import pandas as pd
from dotenv import load_dotenv

from fbs.etl.paths import BRONZE_DIR, bronze_path
from fbs.etl.sharadar.extract import download_table, read_table
from fbs.etl.unify import rename_fields

# %%
# Constants

# This strategy's data folder and the repo root (for .env)
DATA_DIR = Path(__file__).parent / "data"
REPO_ROOT = Path(__file__).resolve().parents[2]

# This strategy (= folder name), the provider and the table of its gold store;
# written as columns into every file under ./data/, so the files join on them
STRATEGY = Path(__file__).parent.name
PROVIDER = "sharadar"
DATASET = "SEP"

# Gold store, ticker -> instrument_id map and sync state
GOLD_DIR = DATA_DIR / "gold" / "EQ" / "spot" / "daily"
MAP_FILE = DATA_DIR / "gold" / "instrument_map.csv"
STATE_FILE = DATA_DIR / "sync_state.json"

# Standard price fields of the gold format; config data.field must be one of them
FIELDS = ["open", "high", "low", "close", "close_raw", "close_adj", "volume"]

# Gold primary key, and all gold columns in file order
KEY = ["strategy", "provider", "dataset", "instrument_id", "timestamp"]
COLUMNS = [*KEY, *FIELDS, "clean_date"]

# Days before the last sync from which updated rows are downloaded again, so a
# row Sharadar updated on the day of the last sync is not missed
OVERLAP_DAYS = 3

# Sessions are dated in New York
NY = "America/New_York"

# %%
# Download

# Sharadar table download into this strategy's bronze folder
def _download(table, /, columns=None, **filters):
    """
    Download one Sharadar table into data/bronze/ and read it back.

    Parameters
    ----------
    table : str
        Sharadar table name: SEP or TICKERS.
    columns : list of str
        Columns to keep. All columns if None.
    **filters
        Nasdaq Data Link filters, e.g. ticker=['AAPL'],
        date={'gte': '2024-01-01'} or lastupdated={'gte': '2026-11-01'}.
        table is positional-only, so TICKERS can be filtered as table='SEP'.

    Returns
    -------
    raw : pd.DataFrame
        The downloaded table, Sharadar column names.
    """

    # Same file name as the repo bronze layer, under this strategy's data folder
    repo_path = bronze_path("Sharadar", "equity_prices", table, date.today(), filters, ".zip",
                            columns=columns)
    path = DATA_DIR / "bronze" / repo_path.relative_to(BRONZE_DIR)

    # Download and read back
    download_table(table, path, columns=columns, overwrite=True, **filters)
    raw = read_table(path)

    return raw

# Ticker to composite FIGI
def _figi_map(symbols):
    """
    Composite FIGI of each symbol, from data/gold/instrument_map.csv; symbols
    not in it are looked up in Sharadar TICKERS and added to it.

    Parameters
    ----------
    symbols : list of str
        Tickers.

    Returns
    -------
    figi : pd.Series
        Index = ticker (in the order of symbols), values = composite FIGI.

    Raises
    ------
    KeyError
        If a ticker has no FIGI.
    """

    # Tickers already mapped
    known = pd.read_csv(MAP_FILE, dtype=str) if MAP_FILE.exists() else pd.DataFrame(
        columns=["strategy", "source", "source_id", "instrument_id"])
    # Files written before the strategy column existed lack it; rewrite them below
    outdated = "strategy" not in known.columns
    known = known.assign(strategy=STRATEGY)[["strategy", "source", "source_id", "instrument_id"]]
    figi = known.loc[known["source"] == "sharadar"].set_index("source_id")["instrument_id"]
    missing = [s for s in symbols if s not in figi.index]

    if missing:
        # TICKERS rows of table SEP; a listed row wins over a delisted one, then the latest
        tickers = _download("TICKERS", columns=["ticker", "figi", "isdelisted", "lastupdated"],
                            table="SEP", ticker=missing)
        tickers = tickers.dropna(subset=["figi"]).sort_values(["isdelisted", "lastupdated"],
                                                              ascending=[True, False])
        found = tickers.drop_duplicates("ticker").set_index("ticker")["figi"]

        # Every ticker needs one
        unmapped = sorted(set(missing) - set(found.index))
        if unmapped:
            raise KeyError(f"Sharadar TICKERS has no FIGI for {unmapped}")

        # Add the new tickers to the map
        added = pd.DataFrame({"strategy": STRATEGY, "source": "sharadar", "source_id": found.index,
                              "instrument_id": found.values})
        MAP_FILE.parent.mkdir(parents=True, exist_ok=True)
        pd.concat([known, added], ignore_index=True).to_csv(MAP_FILE, index=False)
        figi = pd.concat([figi, found])
    elif outdated:
        known.to_csv(MAP_FILE, index=False)

    return figi.loc[symbols]

# %%
# Local Store

# Sync state read
def _load_state():
    """
    Sync state of the local store.

    Returns
    -------
    state : dict
        strategy: this strategy.
        synced: ISO date of the last sync, None if never synced.
        coverage: ticker -> ISO date from which the store holds its rows.
    """

    if not STATE_FILE.exists():
        return {"strategy": STRATEGY, "synced": None, "coverage": {}}

    return {**json.loads(STATE_FILE.read_text()), "strategy": STRATEGY}

# Latest gold file read
def _load_gold():
    """
    The gold store: the latest data/gold/EQ/spot/daily/sharadar_SEP_*.parquet.

    Returns
    -------
    gold : pd.DataFrame
        Gold rows in COLUMNS order; empty if there is no gold file yet.
    """

    files = sorted(GOLD_DIR.glob("sharadar_SEP_*.parquet"))
    if not files:
        return pd.DataFrame(columns=COLUMNS)

    # Files written before the key columns existed lack them
    gold = pd.read_parquet(files[-1]).assign(strategy=STRATEGY, provider=PROVIDER, dataset=DATASET)

    return gold.reindex(columns=COLUMNS)

# SEP rows to the gold format
def _to_gold(sep, figi):
    """
    SEP rows in the gold format.

    Parameters
    ----------
    sep : pd.DataFrame
        SEP rows, Sharadar column names.
    figi : pd.Series
        Index = ticker, values = composite FIGI.

    Returns
    -------
    gold : pd.DataFrame
        COLUMNS: strategy, provider, dataset, instrument_id = composite FIGI,
        timestamp = UTC session close (16:00 New York), then FIELDS;
        clean_date is filled when saved.
    """

    prices = rename_fields(sep, PROVIDER, DATASET)
    close = (prices["timestamp"] + pd.Timedelta(hours=16)).dt.tz_localize(NY)
    gold = pd.DataFrame({"strategy": STRATEGY, "provider": PROVIDER, "dataset": DATASET,
                         "instrument_id": prices["ticker"].map(figi).astype("string"),
                         "timestamp": close.dt.tz_convert("UTC")})
    gold[FIELDS] = prices[FIELDS]

    return gold.reindex(columns=COLUMNS)

# Gold and sync state write
def _save(gold, state):
    """
    Write the gold store as today's file, remove the older gold files, then
    write the sync state.

    Parameters
    ----------
    gold : pd.DataFrame
        The merged gold store.
    state : dict
        The updated sync state.
    """

    # data/gold/EQ/spot/daily/sharadar_SEP_{today}.parquet, written in full before the old files go
    GOLD_DIR.mkdir(parents=True, exist_ok=True)
    today = date.today()
    path = GOLD_DIR / f"sharadar_SEP_{today:%Y%m%d}.parquet"
    tmp = path.with_suffix(".tmp")
    gold.assign(clean_date=today).to_parquet(tmp, index=False)
    tmp.replace(path)
    for old in GOLD_DIR.glob("sharadar_SEP_*.parquet"):
        if old != path:
            old.unlink()

    # The state last, so a failed write leaves the next run to download again
    STATE_FILE.write_text(json.dumps(state, indent=2, sort_keys=True))

# Incremental update of the local store
def _sync(universe, start, figi):
    """
    Download what the local store lacks for the universe from start onward,
    merge it in and save.

    Parameters
    ----------
    universe : list of str
        Tickers.
    start : date
        First session the store must hold for every ticker.
    figi : pd.Series
        Index = ticker, values = composite FIGI.

    Returns
    -------
    gold : pd.DataFrame
        The updated gold store.
    """

    state = _load_state()
    coverage = state["coverage"]
    first = start.isoformat()

    # Tickers to download in full, to backfill, and to update
    new = [t for t in universe if t not in coverage]
    short = [t for t in universe if t in coverage and coverage[t] > first]
    stored = [t for t in universe if t in coverage]

    # Today's sync date is taken before downloading, so rows updated during the download are fetched next time
    today = date.today()
    pieces = []

    # 1. Never stored: every row from start onward
    if new:
        pieces.append(_download("SEP", ticker=new, date={"gte": first}))

    # 2. Stored from a later date: the earlier rows
    if short:
        pieces.append(_download("SEP", ticker=short,
                                date={"gte": first, "lt": max(coverage[t] for t in short)}))

    # 3. Stored: rows updated since the last sync (new sessions and revised history),
    #    not older than the stored history
    if stored and state["synced"]:
        since = date.fromisoformat(state["synced"]) - timedelta(days=OVERLAP_DAYS)
        pieces.append(_download("SEP", ticker=stored, lastupdated={"gte": since.isoformat()},
                                date={"gte": min(coverage[t] for t in stored)}))

    # Merge: a downloaded row replaces the stored row of the same session and instrument
    gold = _load_gold()
    downloaded = [p for p in pieces if not p.empty]
    if downloaded:
        fresh = _to_gold(pd.concat(downloaded, ignore_index=True), figi)
        gold = pd.concat([gold, fresh], ignore_index=True)
        gold["timestamp"] = pd.to_datetime(gold["timestamp"], utc=True)  # an empty store has no dtype
        gold = gold.drop_duplicates(KEY, keep="last")
        gold = gold.sort_values(["timestamp", "instrument_id"], ignore_index=True)

    # New coverage, then save
    for t in new + short:
        coverage[t] = first
    state = {"strategy": STRATEGY, "synced": today.isoformat(), "coverage": coverage}
    _save(gold, state)

    print(f"data: {len(new)} new, {len(short)} backfilled, {len(stored)} updated tickers; "
          f"{sum(len(p) for p in pieces)} rows downloaded")

    return gold

# %%
# Fetch

# Prices of the universe
def fetch(config, start, end):
    """
    Prices of the universe between two sessions, one column per symbol.

    Parameters
    ----------
    config : dict
        config.yaml: universe and data.field are used.
    start, end : date
        First and last session, inclusive.

    Returns
    -------
    prices : pd.DataFrame
        Index = session dates (tz-naive, ascending), Columns = universe
        symbols, values = config data.field.
    """

    universe = list(config["universe"])
    field = config["data"]["field"]
    if field not in FIELDS:
        raise ValueError(f"data.field must be one of {FIELDS}, got {field!r}")
    start, end = pd.Timestamp(start).date(), pd.Timestamp(end).date()

    # API key: nasdaqdatalink reads it at import, possibly before .env was loaded
    load_dotenv(REPO_ROOT / ".env")
    if not os.environ.get("NASDAQ_DATA_LINK_API_KEY"):
        raise RuntimeError("set NASDAQ_DATA_LINK_API_KEY in the environment or the repo-root .env")
    nasdaqdatalink.ApiConfig.api_key = os.environ["NASDAQ_DATA_LINK_API_KEY"]

    # 1-2. Update the local store
    figi = _figi_map(universe)
    gold = _sync(universe, start, figi)

    # 3. The universe's rows, one column per symbol, indexed by New York session date
    ticker = pd.Series(figi.index, index=figi.values)
    rows = gold.loc[gold["instrument_id"].isin(ticker.index)]
    if rows.empty:
        raise ValueError(f"Sharadar SEP has no rows for {universe}")
    rows = rows.assign(date=rows["timestamp"].dt.tz_convert(NY).dt.normalize().dt.tz_localize(None),
                       ticker=rows["instrument_id"].map(ticker))
    prices = rows.pivot(index="date", columns="ticker", values=field).reindex(columns=universe)
    prices = prices.rename_axis(columns=None).sort_index()
    prices = prices.loc[pd.Timestamp(start):pd.Timestamp(end)]
    if prices.empty:
        raise ValueError(f"Sharadar SEP has no rows for {start} to {end}")

    return prices
