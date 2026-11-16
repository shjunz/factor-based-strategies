"""One paper-trading run for one strategy.

Timing (matches a close-to-close backtest with a one-session execution lag):
    signal session t  = the last completed session; data must include it
    exec session t+1  = today (if the market is open) or the next session
    orders            = market-on-close (time_in_force=cls) on t+1
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from dataclasses import asdict
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd

from fbs.live import checks
from fbs.live.broker import AlpacaBroker
from fbs.live.loader import Strategy, load_strategy
from fbs.live.plan import clean_targets, plan_orders, rebalance_sessions, turnover

NY = ZoneInfo("America/New_York")


def _git_sha() -> str:
    try:
        sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True).stdout.strip()
        return f"{sha}{'-dirty' if dirty else ''}" or "unknown"
    except OSError:
        return "unknown"


def _write_record(strategy: Strategy, record: dict) -> Path:
    folder = strategy.folder / "records"
    folder.mkdir(exist_ok=True)
    kind = "rebalance" if record["mode"] == "submit" else "dryrun"
    path = folder / f"{record['exec_session']}-{kind}.json"
    path.write_text(json.dumps(record, indent=2, default=str))
    print(f"record: {path.relative_to(strategy.folder.parents[1])}")
    return path


def _write_report(strategy: Strategy, record_path: Path, record: dict, signal: date,
                  data: pd.DataFrame | None, frame: pd.DataFrame | None) -> None:
    """Dry-run PDF next to the record. Backtests from config backtest_start when set, else on the run's data.
    A failed report never changes the run's outcome."""
    try:
        from fbs.live import report
        start = strategy.config.get("backtest_start")
        if start and frame is not None:
            data = strategy.data.fetch(strategy.config, pd.Timestamp(start).date(), signal)
            frame = strategy.weights.compute(data, strategy.config["params"])
        path = report.write_report(record_path.with_suffix(".pdf"), strategy, record, data, frame)
        print(f"report: {path.relative_to(strategy.folder.parents[1])}")
    except Exception as exc:   # the record is already written; the report is a convenience
        print(f"report not written: {exc}")


def _sessions_around(broker, today: date, lookback: int) -> list[date]:
    start = today - timedelta(days=int(lookback * 1.6) + 30)
    return broker.sessions(start, today + timedelta(days=10))


def rebalance(name: str, submit: bool = False, asof: date | None = None, force: bool = False,
              broker=None) -> int:
    """Plan (and optionally submit) today's orders. Returns a process exit code."""
    s = load_strategy(name)
    limits = s.paper["limits"]
    capital = float(s.paper["capital"])
    broker = broker or AlpacaBroker(s.paper["account"], s.paper.get("mode", "paper"))

    clock = broker.clock()
    now = clock.timestamp.astimezone(NY)
    today = now.date()
    sessions = _sessions_around(broker, today, int(s.config["lookback_sessions"]))

    # 1. Which session's signal, executed on which session?
    if asof is not None:
        if submit:
            raise ValueError("--asof is for dry runs only; --submit always trades today's session")
        if asof not in sessions:
            raise ValueError(f"{asof} is not a trading session")
        signal = asof
        exec_session = next(d for d in sessions if d > asof)
    else:
        exec_session = today if clock.is_open else clock.next_open.astimezone(NY).date()
        signal = max(d for d in sessions if d < exec_session)

    record = {
        "strategy": name, "mode": "submit" if submit else "dry_run",
        "signal_session": signal.isoformat(), "exec_session": exec_session.isoformat(),
        "run_at": now.isoformat(), "git": _git_sha(), "status": None,
        "failures": [], "notes": [], "targets": {}, "orders": [], "submitted": [],
    }
    print(f"{name}: signal session {signal}, execution at the close of {exec_session}")

    # 2. Is this a rebalance session?
    if signal not in rebalance_sessions(sessions, s.config["rebalance"]) and not force:
        print(f"not a rebalance session for rule '{s.config['rebalance']}': nothing to do")
        return 0

    # 3. Data → target weights, using the strategy's own code
    idx = sessions.index(signal)
    start = sessions[max(0, idx - int(s.config["lookback_sessions"]) + 1)]
    data = s.data.fetch(s.config, start, signal)
    failures = checks.check_data(data, signal)
    weights = pd.Series(dtype=float)
    frame = None
    if not failures:
        frame = s.weights.compute(data, s.config["params"])
        key = pd.Timestamp(signal)
        if key not in frame.index:
            failures.append(f"weights have no row for {signal}")
        else:
            weights = frame.loc[key].dropna()
            weights = weights[weights != 0]
            failures += checks.check_weights(weights, limits)
    record["targets"] = {k: round(float(v), 6) for k, v in weights.items()}

    # 4. Account, positions, prices → orders
    orders, notes = [], []
    prices: dict[str, float] = {}
    if not failures:
        account = broker.account()
        failures += checks.check_account(account, capital)
        positions = broker.positions()
        symbols = sorted(set(weights.index) | set(positions))
        assets = {sym: broker.asset(sym) for sym in symbols}
        targets, notes = clean_targets(weights, assets, limits["allow_shorts"])
        prices = broker.latest_prices(symbols)
        orders, plan_notes = plan_orders(targets, positions, prices, capital, account.buying_power,
                                         float(limits["min_order_notional"]), name, exec_session)
        notes += plan_notes
        to = turnover(orders, prices, capital)
        record["turnover"] = round(to, 4)
        failures += checks.check_orders(orders, prices, to, limits)
    record["orders"] = [asdict(o) for o in orders]
    record["notes"] = notes
    record["failures"] = failures

    _print_plan(orders, prices, notes, failures)
    if failures:
        record["status"] = "blocked"
        path = _write_record(s, record)
        if not submit:
            _write_report(s, path, record, signal, data, frame)
        return 1
    if not submit:
        record["status"] = "dry_run"
        path = _write_record(s, record)
        _write_report(s, path, record, signal, data, frame)
        return 0

    # 5. Submit: enabled, inside the window, and never twice
    gate = []
    if not s.paper["enabled"]:
        gate.append("paper.yaml enabled is false")
    if not clock.is_open:
        gate.append("market is closed")
    minutes_left = (clock.next_close - clock.timestamp).total_seconds() / 60
    cutoff = float(s.paper.get("moc_cutoff_minutes", 15))
    if clock.is_open and minutes_left < cutoff:
        gate.append(f"only {minutes_left:.0f} min to the close; MOC cut-off buffer is {cutoff:.0f} min")
    if gate:
        record["status"] = "blocked"
        record["failures"] = gate
        print("NOT SUBMITTED: " + "; ".join(gate))
        _write_record(s, record)
        return 1

    prefix = f"{name}-{exec_session.isoformat()}-"
    existing = {o.client_order_id for o in broker.orders_with_prefix(prefix, clock.timestamp - timedelta(days=3))}
    for o in orders:
        if o.client_order_id in existing:
            record["submitted"].append({"client_order_id": o.client_order_id, "status": "already_present"})
            continue
        try:
            status = broker.submit_moc(o)
        except Exception as exc:   # one rejected order must not stop the others
            status = f"rejected: {exc}"
        record["submitted"].append({"client_order_id": o.client_order_id, "status": status})
        print(f"  {o.client_order_id}: {status}")

    rejected = [x for x in record["submitted"] if x["status"].startswith("rejected")]
    record["status"] = "partial" if rejected else "submitted"
    _write_record(s, record)
    return 1 if rejected else 0


def _print_plan(orders, prices, notes, failures) -> None:
    if orders:
        print(f"{'side':<5} {'qty':>7} {'symbol':<8} {'~notional':>12}  client_order_id")
        for o in orders:
            print(f"{o.side:<5} {o.qty:>7} {o.symbol:<8} {o.qty * prices.get(o.symbol, 0):>12,.0f}  {o.client_order_id}")
    else:
        print("no orders: positions already match targets")
    for n in notes:
        print(f"note: {n}")
    for f in failures:
        print(f"BLOCKED: {f}")


def status(name: str, broker=None) -> int:
    s = load_strategy(name)
    broker = broker or AlpacaBroker(s.paper["account"], s.paper.get("mode", "paper"))
    acct = broker.account()
    print(f"{name} · account {s.paper['account']} · equity {acct.equity:,.2f} · buying power {acct.buying_power:,.2f}"
          f" · status {acct.status}")
    positions = broker.positions()
    print(f"positions ({len(positions)}): " + ", ".join(f"{k} {v}" for k, v in sorted(positions.items())))
    since = broker.clock().timestamp - timedelta(days=7)
    for o in broker.orders_with_prefix(f"{name}-", since):
        print(f"  {o.client_order_id}: {o.status} filled {o.filled_qty} @ {o.filled_avg_price}")
    return 0


def halt(name: str, flatten: bool = False, broker=None) -> int:
    s = load_strategy(name)
    broker = broker or AlpacaBroker(s.paper["account"], s.paper.get("mode", "paper"))
    if flatten:
        broker.close_all_positions()
        print(f"{name}: cancelled open orders and sent orders to close all positions")
    else:
        broker.cancel_all()
        print(f"{name}: cancelled all open orders; set enabled: false in paper.yaml to stop future runs")
    return 0


def parse_date(text: str | None) -> date | None:
    return datetime.strptime(text, "%Y-%m-%d").date() if text else None
