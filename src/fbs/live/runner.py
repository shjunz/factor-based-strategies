'''
runner.py - Paper-trading commands for one strategy, called by __main__.py.

Commands:
    rebalance    backtest, check and plan the orders that move the account to
                 the target weights; dry run by default, --submit sends them.
                 The first run on an empty account is the initial build.
    status       print the account, positions and the last week's orders
    performance  post-trade, after the close: fills of the submitted orders and
                 live results against the backtest of the same sessions, as
                 the live report PDF in records/
    halt         cancel all open orders; with flatten=True also close every
                 position (the CLI's `flatten` command)

Timing of rebalance (matches a close-to-close backtest with a one-session
execution lag):
    signal session t  = the last completed session; data must include it
    exec session t+1  = today (if the market is open) or the next session
    orders            = market-on-close (time_in_force=cls) on t+1

rebalance runs these steps in order; a failure in steps 4 to 6 blocks the run
(no orders) and goes straight to step 7:

    Step 1: Pick the sessions.
        The execution session is today if the market is open now, otherwise
        the next day the market opens. The signal session is the trading
        day before the execution session. A dry run with --asof uses the
        given day as the signal session and the next trading day as the
        execution session.

    Step 2: Stop early if there is nothing to do.
        With --submit, stop if today is a weekend or holiday. Then stop if
        the signal session is not a rebalance day under config `rebalance`
        (e.g. a monthly rule only rebalances on the last session of the
        month). --force skips the second check.

    Step 3: Compute the weights.
        The strategy's data.py downloads data up to the signal session, and
        its weights.py computes the target weight of every asset on every
        session.

    Step 4: Backtest (fbs.backtesting), the gate to everything after it.
        Backtest the weights from config `backtest_start` (else on the run's
        own data) to the signal session and write the backtest report,
        records/{exec_session}-backtest_IS-..._OOS-....pdf (the IS / OOS
        dates are in the name). Block the run if the
        backtest cannot be computed or the report cannot be written.

    Step 5: Pre-trade checks (fbs.risk.pre_trade) on the data and weights.
        Keep the signal session's non-zero weights. Block the run if the data
        does not reach the signal session or a weight breaks the limits in
        config.yaml paper.

    Step 6: Orders (fbs.execution), then the pre-trade order check.
        Read the account, the current positions and the latest prices from
        the broker (config.yaml paper.broker). Block if the account is not
        usable. Drop assets the broker cannot trade, then compare target and
        current shares and plan whole-share buy and sell orders. Block the
        run if the orders break the limits (count, size, turnover).

    Step 7: Dry run or blocked: write records/{exec_session}-rebalance.json
        (mode dry_run or submit, status dry_run or blocked) and stop.

    Step 8: Submit the orders (fbs.execution, --submit only).
        Check that config.yaml `paper.enabled` is true, the market is open, and
        there are more than `moc_cutoff_minutes` before the close. Skip
        orders already sent for this execution session (same
        client_order_id), so running twice never trades twice. Send the rest
        as market-on-close orders, filled at today's closing price, and
        write records/{exec_session}-rebalance.json. The after-close
        `performance` command reads it.

Post-trade (fbs.risk.post_trade) is not part of rebalance: the orders fill at
the close, after this run ends. Schedule `performance` after the close.
'''

# %%
# Imports

import json
from dataclasses import asdict
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd

from fbs import risk
from fbs.backtesting import BARS_PER_YEAR, backtest
from fbs.execution import (execution_plan_orders, execution_rebalance_sessions,
                           execution_remove_invalid_assets, execution_submit,
                           execution_submit_gate, execution_turnover)
from fbs.live.brokers import make_broker
from fbs.live.loader import load_strategy

# %%
# Constants

# Exchange time zone: sessions are New York dates
NY = ZoneInfo("America/New_York")

# %%
# Helpers

# Command line date
def parse_date(text):
    """
    Parse a YYYY-MM-DD command line date.

    Parameters
    ----------
    text : str or None
        Date text.

    Returns
    -------
    day : date or None
        None if `text` is empty.

    Examples
    --------
    >>> parse_date("2024-12-31")
    datetime.date(2024, 12, 31)
    >>> parse_date(None) is None
    True
    """

    day = datetime.strptime(text, "%Y-%m-%d").date() if text else None

    return day

# Run record
def _write_record(strategy, record):
    """
    Write the run record to records/{exec_session}-rebalance.json. A dry run
    and a --submit run use the same name; `mode` inside tells them apart. A
    dry run never overwrites a submitted record of the same session, since
    performance finds the first live trade from it.

    Parameters
    ----------
    strategy : Strategy
        The loaded strategy.
    record : dict
        The run record.

    Returns
    -------
    path : Path or None
        The written file, None if a submitted record was kept.

    Examples
    --------
    >>> import tempfile
    >>> from dataclasses import replace
    >>> from pathlib import Path
    >>> folder = Path(tempfile.mkdtemp()) / "strategy" / "demo"
    >>> folder.mkdir(parents=True)
    >>> demo = replace(load_strategy("strategy_example"), name="demo", folder=folder)
    >>> record = {"mode": "submit", "signal_session": "2024-12-30",
    ...           "exec_session": "2024-12-31", "run_at": "2024-12-31T15:00:00-05:00",
    ...           "status": "submitted", "failures": [], "notes": [],
    ...           "targets": {"SPY": 0.5}, "orders": [], "submitted": []}
    >>> _write_record(demo, record).name
    record: strategy/demo/records/2024-12-31-rebalance.json
    '2024-12-31-rebalance.json'

    A later dry run for the same session keeps the submitted record:

    >>> _write_record(demo, {**record, "mode": "dry_run", "status": "dry_run"}) is None
    record not written: strategy/demo/records/2024-12-31-rebalance.json is a submitted run
    True
    """

    folder = strategy.folder / "records"
    folder.mkdir(exist_ok=True)
    path = folder / f"{record['exec_session']}-rebalance.json"
    shown = path.relative_to(strategy.folder.parents[1])
    if record["mode"] != "submit" and path.exists():
        if json.loads(path.read_text()).get("status") in ("submitted", "partial"):
            print(f"record not written: {shown} is a submitted run")
            return None
    path.write_text(json.dumps(record, indent=2, default=str))
    print(f"record: {shown}")

    return path

# Step 4: backtest gate
def _backtest_gate(strategy, record, signal, data, frame):
    """
    Backtest the weights up to the signal session and write the backtest
    report PDF. Any problem is a failure that blocks the run.

    Parameters
    ----------
    strategy : Strategy
        The loaded strategy.
    record : dict
        The run record: mode and exec_session name the PDF.
    signal : date
        Signal session, the backtest's last day.
    data : pd.DataFrame
        The run's data.
    frame : pd.DataFrame or None
        The run's weights, None if they could not be computed.

    Returns
    -------
    failures : list of str
        Empty if the backtest ran and its report was written.

    Examples
    --------
    >>> import tempfile
    >>> from dataclasses import replace
    >>> from datetime import date
    >>> from pathlib import Path
    >>> import numpy as np
    >>> folder = Path(tempfile.mkdtemp()) / "strategy" / "demo"
    >>> folder.mkdir(parents=True)
    >>> s = load_strategy("strategy_example")
    >>> demo = replace(s, name="demo", folder=folder,
    ...                config={k: v for k, v in s.config.items() if k not in ("backtest_start", "split")})
    >>> record = {"mode": "dry_run", "exec_session": "2024-12-31"}
    >>> idx = pd.bdate_range("2024-10-01", periods=60)
    >>> prices = pd.DataFrame({"SPY": np.linspace(570, 590, 60),
    ...                        "QQQ": np.linspace(490, 515, 60)}, index=idx)
    >>> weights = pd.DataFrame(0.5, index=idx, columns=prices.columns)
    >>> _backtest_gate(demo, record, date(2024, 12, 20), prices, weights)
    report: strategy/demo/records/2024-12-31-backtest_FULL-20241104-20241223.pdf
    []

    No weights, or too little history, blocks the run:

    >>> _backtest_gate(demo, record, date(2024, 12, 20), prices, None)
    ['backtest: no weights to backtest']
    >>> _backtest_gate(demo, record, date(2024, 12, 20), prices.iloc[:2], weights.iloc[:2])
    ['backtest: fewer than 2 sessions with positions']
    """

    if frame is None:
        return ["backtest: no weights to backtest"]

    try:
        # Longer history for the backtest when config asks for it
        start = strategy.config.get("backtest_start")
        if start:
            data = strategy.data.fetch(strategy.config, pd.Timestamp(start).date(), signal)
            frame = strategy.weights.compute(data, strategy.config["params"])
        bt = backtest(data, frame, strategy.config["rebalance"])
        if len(bt) < 2:
            return ["backtest: fewer than 2 sessions with positions"]

        from fbs.backtesting.backtest_report import backtest_report_name, write_backtest_report

        folder = strategy.folder / "records"
        folder.mkdir(exist_ok=True)
        name = backtest_report_name(record["exec_session"], bt, strategy.config.get("split"))
        path = write_backtest_report(folder / name, strategy, bt)
        record["backtest_report"] = name
        print(f"report: {path.relative_to(strategy.folder.parents[1])}")
    except Exception as exc:
        return [f"backtest: {type(exc).__name__}: {exc}"]

    return []

# %%
# Rebalance Steps

# Step 1: signal and execution sessions
def _pick_sessions(clock, sessions, asof, submit):
    """
    Signal session t and execution session t+1.

    Parameters
    ----------
    clock : MarketClock
        Market clock.
    sessions : list of date
        Trading sessions around today.
    asof : date or None
        Past signal session for a dry run. None for today's run.
    submit : bool
        True if orders will be sent.

    Returns
    -------
    signal, exec_session : date
        Signal session t and execution session t+1.

    Examples
    --------
    >>> from datetime import date
    >>> sessions = [date(2024, 12, 27), date(2024, 12, 30), date(2024, 12, 31), date(2025, 1, 2)]
    >>> from types import SimpleNamespace as Clock
    >>> open_clock = Clock(timestamp=datetime(2024, 12, 31, 10, 0, tzinfo=NY), is_open=True,
    ...                    next_open=datetime(2025, 1, 2, 9, 30, tzinfo=NY),
    ...                    next_close=datetime(2024, 12, 31, 16, 0, tzinfo=NY))

    Market open on 2024-12-31: execute today, signal is the session before.

    >>> _pick_sessions(open_clock, sessions, None, submit=False)
    (datetime.date(2024, 12, 30), datetime.date(2024, 12, 31))

    Dry run for a past signal session:

    >>> _pick_sessions(open_clock, sessions, date(2024, 12, 27), submit=False)
    (datetime.date(2024, 12, 27), datetime.date(2024, 12, 30))
    """

    # Dry run for a past signal session
    if asof is not None:
        if submit:
            raise ValueError("--asof is for dry runs only; --submit always trades today's session")
        if asof not in sessions:
            raise ValueError(f"{asof} is not a trading session")
        exec_session = next(d for d in sessions if d > asof)
        return asof, exec_session

    # Today: execute today if the market is open, else at the next open; signal is the session before
    now = clock.timestamp.astimezone(NY)
    exec_session = now.date() if clock.is_open else clock.next_open.astimezone(NY).date()
    signal = max(d for d in sessions if d < exec_session)

    return signal, exec_session

# Step 3: data -> weights of every session
def _strategy_weights(strategy, sessions, signal):
    """
    Fetch the data and compute the weights of every session.

    Parameters
    ----------
    strategy : Strategy
        The loaded strategy.
    sessions : list of date
        Trading sessions around the signal session.
    signal : date
        Signal session.

    Returns
    -------
    data : pd.DataFrame
        Output of data.fetch.
    frame : pd.DataFrame or None
        Output of weights.compute, None if there is no data.

    Examples
    --------
    >>> from datetime import date
    >>> from dataclasses import replace
    >>> from types import SimpleNamespace as Module
    >>> sessions = [date(2024, 12, 27), date(2024, 12, 30), date(2024, 12, 31)]
    >>> prices = pd.DataFrame({"SPY": [595.0, 588.0], "QQQ": [522.0, 515.0]},
    ...                       index=pd.to_datetime(["2024-12-27", "2024-12-30"]))
    >>> s = load_strategy("strategy_example")
    >>> demo = replace(s, config={**s.config, "lookback_sessions": 2},
    ...                data=Module(fetch=lambda config, start, end: prices),
    ...                weights=Module(compute=lambda data, params: data * 0 + 0.5))
    >>> data, frame = _strategy_weights(demo, sessions, date(2024, 12, 30))
    >>> frame.shape
    (2, 2)
    """

    # Data for the last lookback_sessions sessions up to the signal session
    lookback = int(strategy.config["lookback_sessions"])
    start = sessions[max(0, sessions.index(signal) - lookback + 1)]
    data = strategy.data.fetch(strategy.config, start, signal)
    if data is None or len(data) == 0:
        return data, None

    frame = strategy.weights.compute(data, strategy.config["params"])

    return data, frame

# Step 5: pre-trade checks on the data and the signal session's weights
def _signal_weights(strategy, data, frame, signal):
    """
    Check the data, take the signal session's non-zero weights and check them.

    Parameters
    ----------
    strategy : Strategy
        The loaded strategy.
    data : pd.DataFrame
        Output of data.fetch.
    frame : pd.DataFrame or None
        Output of weights.compute.
    signal : date
        Signal session.

    Returns
    -------
    weights : pd.Series
        Non-zero target weights of the signal session.
    failures : list of str
        Data and weights check failures.

    Examples
    --------
    >>> from datetime import date
    >>> from dataclasses import replace
    >>> prices = pd.DataFrame({"SPY": [595.0, 588.0], "QQQ": [522.0, 515.0]},
    ...                       index=pd.to_datetime(["2024-12-27", "2024-12-30"]))
    >>> s = load_strategy("strategy_example")
    >>> demo = replace(s, paper={**s.paper, "limits": {**s.paper["limits"], "max_weight": 0.5}})
    >>> weights, failures = _signal_weights(demo, prices, prices * 0 + 0.5, date(2024, 12, 30))
    >>> weights.to_dict(), failures
    ({'SPY': 0.5, 'QQQ': 0.5}, [])

    Data that stops before the signal session blocks the run:

    >>> _signal_weights(demo, prices, prices * 0 + 0.5, date(2024, 12, 31))[1]
    ['stale data: last session 2024-12-30, expected 2024-12-31']
    """

    failures = risk.risk_input_data(data, signal)
    if failures:
        return pd.Series(dtype=float), failures

    if frame is None or pd.Timestamp(signal) not in frame.index:
        return pd.Series(dtype=float), [f"weights have no row for {signal}"]
    weights = frame.loc[pd.Timestamp(signal)].dropna()
    weights = weights[weights != 0]
    failures = risk.risk_weights(weights, strategy.paper["limits"])

    return weights, failures

# Step 6: account, positions, prices -> orders
def _plan(strategy, broker, weights, exec_session):
    """
    Read the account and plan the orders that move it to the target weights.

    Parameters
    ----------
    strategy : Strategy
        The loaded strategy.
    broker : Broker
        The strategy's broker.
    weights : pd.Series
        Target weights of the signal session.
    exec_session : date
        Execution session.

    Returns
    -------
    orders : list of OrderIntent
        Planned orders.
    prices : dict of str to float
        Latest price per symbol.
    notes : list of str
        Dropped symbols, skipped trades and scaling.
    failures : list of str
        Account check failures.

    Examples
    --------
    >>> from dataclasses import replace
    >>> from datetime import date
    >>> from types import SimpleNamespace as Broker
    >>> from fbs.live.brokers import AccountState, AssetInfo
    >>> broker = Broker(
    ...     account=lambda: AccountState(100_000, 200_000, True, False, False, "ACTIVE"),
    ...     positions=lambda: {"SPY": 100},
    ...     assets=lambda symbols: {s: AssetInfo(True, True, True) for s in symbols},
    ...     latest_prices=lambda symbols: {"SPY": 500.0, "QQQ": 400.0})
    >>> s = load_strategy("strategy_example")
    >>> demo = replace(s, name="demo", paper={**s.paper, "capital": 100_000})
    >>> orders, prices, notes, failures = _plan(demo, broker, pd.Series({"SPY": 0.5, "QQQ": 0.5}),
    ...                                         date(2024, 12, 31))
    >>> [(o.side, o.symbol, o.qty, o.client_order_id) for o in orders], failures
    ([('buy', 'QQQ', 125, 'demo-2024-12-31-QQQ-adjust')], [])
    """

    limits = strategy.paper["limits"]
    capital = float(strategy.paper["capital"])

    # Account
    account = broker.account()
    failures = risk.risk_account(account, capital)

    # Targets that can be traded at the broker
    positions = broker.positions()
    symbols = sorted(set(weights.index) | set(positions))
    assets = broker.assets(symbols)
    targets, notes = execution_remove_invalid_assets(weights, assets, limits["allow_shorts"])

    # Whole-share orders at the latest prices
    prices = broker.latest_prices(symbols)
    orders, plan_notes = execution_plan_orders(targets, positions, prices, capital, account.buying_power,
                                     float(limits["min_order_notional"]), strategy.name, exec_session)
    notes += plan_notes

    return orders, prices, notes, failures

# %%
# Commands

# Rebalance
def rebalance(name, submit=False, asof=None, force=False):
    """
    Plan, and optionally submit, one rebalance of a strategy.

    Parameters
    ----------
    name : str
        Folder name under strategy/.
    submit : bool
        Send the orders. Dry run if False.
    asof : date or None
        Past signal session for a dry run. None for today's run.
    force : bool
        Run even if the signal session is not a rebalance session.

    Returns
    -------
    code : int
        Process exit code: 0 for a dry run, a submitted run or nothing to do,
        1 for a blocked or partly rejected run.

    Examples
    --------
    Needs the broker connection and data API keys, so these calls are not run here:

    >>> rebalance("strategy_example")  # doctest: +SKIP
    strategy_example: signal session 2024-12-30, execution at the close of 2024-12-31
    ...
    0
    >>> rebalance("strategy_example", asof=date(2024, 11, 29), force=True)  # doctest: +SKIP
    strategy_example: signal session 2024-11-29, execution at the close of 2024-12-02
    ...
    0
    """

    s = load_strategy(name)
    broker = make_broker(s)
    clock = broker.clock()
    now = clock.timestamp.astimezone(NY)

    # Sessions around today, enough to cover lookback_sessions
    lookback = int(s.config["lookback_sessions"])
    sessions = broker.sessions(now.date() - timedelta(days=int(lookback * 1.6) + 30),
                               now.date() + timedelta(days=10))

    # 1. Signal and execution sessions
    signal, exec_session = _pick_sessions(clock, sessions, asof, submit)
    print(f"{name}: signal session {signal}, execution at the close of {exec_session}")
    record = {
        "strategy": name, "mode": "submit" if submit else "dry_run",
        "signal_session": signal.isoformat(), "exec_session": exec_session.isoformat(),
        "run_at": now.isoformat(), "status": None,
        "failures": [], "notes": [], "targets": {}, "orders": [], "submitted": [],
    }

    # 2. Stop on a weekend or holiday (a scheduled --submit run has nothing to do),
    #    and unless the signal session is a rebalance session
    if submit and now.date() not in sessions:
        print(f"{now.date()} is not a trading session: nothing to do")
        return 0
    if signal not in execution_rebalance_sessions(sessions, s.config["rebalance"]) and not force:
        print(f"not a rebalance session for rule '{s.config['rebalance']}': nothing to do")
        return 0

    # 3. Data -> weights of every session
    data, frame = _strategy_weights(s, sessions, signal)

    # 4. Backtest and its report: the gate to everything after it
    failures = _backtest_gate(s, record, signal, data, frame)

    # 5. Pre-trade: data and the signal session's weights
    if not failures:
        weights, failures = _signal_weights(s, data, frame, signal)
        record["targets"] = {k: round(float(v), 6) for k, v in weights.items()}

    # 6. Execution: account, positions, prices -> orders; then pre-trade: the orders
    if not failures:
        orders, prices, notes, failures = _plan(s, broker, weights, exec_session)
        to = execution_turnover(orders, prices, float(s.paper["capital"]))
        record["turnover"] = round(to, 4)
        record["orders"] = [asdict(o) for o in orders]
        record["notes"] = notes
        failures += risk.risk_orders(orders, prices, to, s.paper["limits"])
    record["failures"] = failures

    # 7. Dry run or blocked: write the record, stop
    if failures or not submit:
        record["status"] = "blocked" if failures else "dry_run"
        if failures:
            print("BLOCKED: " + "; ".join(failures))
        _write_record(s, record)
        return 1 if failures else 0

    # 8. Execution: submit if enabled, inside the window, and never twice
    gate = execution_submit_gate(s.paper, clock)
    if gate:
        record["status"] = "blocked"
        record["failures"] = gate
        print("NOT SUBMITTED: " + "; ".join(gate))
        _write_record(s, record)
        return 1
    record["submitted"] = execution_submit(broker, orders, f"{name}-{exec_session.isoformat()}-",
                                           clock.timestamp - timedelta(days=3))
    rejected = [x for x in record["submitted"] if x["status"].startswith("rejected")]
    record["status"] = "partial" if rejected else "submitted"
    _write_record(s, record)

    return 1 if rejected else 0

# Status
def status(name):
    """
    Print the account, positions and the last week's orders of a strategy.

    Parameters
    ----------
    name : str
        Folder name under strategy/.

    Returns
    -------
    code : int
        Always 0.

    Examples
    --------
    Needs the account's broker connection:

    >>> status("strategy_example")  # doctest: +SKIP
    strategy_example · alpaca account STRATEGY_EXAMPLE · equity 100,412.37 · buying power 191,204.11 · status ACTIVE
    positions (2): QQQ 125, SPY 100
      strategy_example-2024-12-31-QQQ-adjust: filled filled 125.0 @ 511.2
    0
    """

    s = load_strategy(name)
    broker = make_broker(s)

    # Account
    acct = broker.account()
    print(f"{name} · {s.paper.get('broker', 'alpaca')} account {s.paper['account']} · equity {acct.equity:,.2f} · buying power {acct.buying_power:,.2f}"
          f" · status {acct.status}")

    # Positions
    positions = broker.positions()
    print(f"positions ({len(positions)}): " + ", ".join(f"{k} {v}" for k, v in sorted(positions.items())))

    # This strategy's orders of the last 7 days
    since = broker.clock().timestamp - timedelta(days=7)
    for o in broker.orders_with_prefix(f"{name}-", since):
        print(f"  {o.client_order_id}: {o.status} filled {o.filled_qty} @ {o.filled_avg_price}")

    return 0

# First live trade
def _first_exec(strategy):
    """
    Execution session of the first rebalance that sent orders, from the
    records.

    Parameters
    ----------
    strategy : Strategy
        The loaded strategy.

    Returns
    -------
    day : date or None
        None if no rebalance has been submitted yet.

    Examples
    --------
    >>> import tempfile
    >>> from dataclasses import replace
    >>> from pathlib import Path
    >>> folder = Path(tempfile.mkdtemp()) / "strategy" / "demo"
    >>> folder.mkdir(parents=True)
    >>> demo = replace(load_strategy("strategy_example"), name="demo", folder=folder)
    >>> _first_exec(demo) is None
    True
    >>> (folder / "records").mkdir()
    >>> _ = (folder / "records" / "2024-12-31-rebalance.json").write_text(
    ...     json.dumps({"status": "submitted", "exec_session": "2024-12-31"}))
    >>> _ = (folder / "records" / "2025-01-31-rebalance.json").write_text(
    ...     json.dumps({"status": "blocked", "exec_session": "2025-01-31"}))
    >>> _first_exec(demo)
    datetime.date(2024, 12, 31)
    """

    days = []
    for path in (strategy.folder / "records").glob("*-rebalance.json"):
        record = json.loads(path.read_text())
        if record.get("status") in ("submitted", "partial"):
            days.append(parse_date(record["exec_session"]))
    day = min(days) if days else None

    return day

# Performance
def performance(name, start=None):
    """
    Live results since the first submitted rebalance against the backtest of
    the same sessions: print a summary and write
    records/{last_session}-live-trading.pdf.

    Parameters
    ----------
    name : str
        Folder name under strategy/.
    start : date or None
        Execution session of the first live trade. None to take it from the
        records.

    Returns
    -------
    code : int
        0 if the PDF was written, 1 if there is nothing to compare yet.

    Examples
    --------
    Needs the broker connection and data API keys, so these calls are not run here:

    >>> performance("strategy_example")  # doctest: +SKIP
    strategy_example: live 0.41%, backtest 0.38%, equal-weight 0.12% over 2 sessions; tracking error 0.52%
    orders 2, not fully filled 0, slippage 0.6 bps (3 USD)
    report: strategy/strategy_example/records/2024-12-31-live-trading.pdf
    0
    >>> performance("strategy_example", start=date(2024, 12, 2))  # doctest: +SKIP
    0
    """

    from fbs.risk.post_trade.live_report import write_live_report

    s = load_strategy(name)
    broker = make_broker(s)
    clock = broker.clock()
    now = clock.timestamp.astimezone(NY)
    capital = float(s.paper["capital"])

    # Live period: first trade to the last completed session
    first = start or _first_exec(s)
    if first is None:
        print(f"{name}: no submitted rebalance in records/; pass --start YYYY-MM-DD")
        return 1
    lookback = int(s.config["lookback_sessions"])
    sessions = broker.sessions(first - timedelta(days=int(lookback * 1.6) + 30), now.date())
    done_today = (now.date() in sessions and not clock.is_open
                  and clock.next_open.astimezone(NY).date() > now.date())
    last = now.date() if done_today else max(d for d in sessions if d < now.date())

    # Live daily returns = change in account equity / paper.capital, from the
    # session after the first trade (the first one holding positions all day)
    equity = broker.equity_history(first)
    live = (equity.diff() / capital).dropna()
    live = live[live.index > pd.Timestamp(first)]

    # Backtest of the same sessions, with lookback_sessions of history before the first trade
    before = [d for d in sessions if d <= first]
    data = s.data.fetch(s.config, before[max(0, len(before) - lookback)], last)
    frame = s.weights.compute(data, s.config["params"])
    bt = backtest(data, frame, s.config["rebalance"])
    # Live, backtest and benchmark returns on the sessions all of them have
    cmp = pd.DataFrame({"live": live, "backtest": bt["strategy"], "benchmark": bt["benchmark"]}).dropna()
    if len(cmp) < 2:
        print(f"{name}: fewer than 2 sessions with both live and backtest returns since {first}; nothing to compare")
        return 1

    # Post-trade: fills against the close
    orders = broker.orders_with_prefix(f"{name}-", datetime.combine(first, datetime.min.time(), tzinfo=NY)
                                       - timedelta(days=3))
    closes = broker.daily_closes(sorted({o.symbol for o in orders}), first, last)
    ex = risk.risk_fills(orders, closes, name)
    summary = risk.risk_fill_summary(ex)

    # Terminal summary
    acct = broker.account()
    cum = (1 + cmp).prod() - 1
    gap = cmp["live"] - cmp["backtest"]
    info = [
        f"Live since: close of {first}    Through: {cmp.index[-1].date()}    Sessions: {len(cmp)}",
        f"Account {s.paper['account']}    Equity {acct.equity:,.0f} USD    Capital {capital:,.0f} USD"
        f"    Rebalance {s.config['rebalance']}",
        f"Run at: {now.isoformat()[:19]}",
    ]
    print(f"{name}: live {cum['live']:.2%}, backtest {cum['backtest']:.2%}, equal-weight {cum['benchmark']:.2%}"
          f" over {len(cmp)} sessions; tracking error {gap.std() * BARS_PER_YEAR ** 0.5:.2%}")
    print(f"orders {summary['orders']}, not fully filled {summary['not_filled']}, "
          f"slippage {summary['slippage_bps']:.1f} bps ({summary['slippage_usd']:,.0f} USD)")

    # PDF
    folder = s.folder / "records"
    folder.mkdir(exist_ok=True)
    path = write_live_report(folder / f"{cmp.index[-1].date()}-live-trading.pdf", s, info, cmp, ex)
    print(f"report: {path.relative_to(s.folder.parents[1])}")

    return 0

# Halt
def halt(name, flatten=False):
    """
    Cancel all open orders, and with `flatten` also close all positions.

    Parameters
    ----------
    name : str
        Folder name under strategy/.
    flatten : bool
        Also close every position.

    Returns
    -------
    code : int
        Always 0.

    Examples
    --------
    Needs the account's broker connection:

    >>> halt("strategy_example")  # doctest: +SKIP
    strategy_example: cancelled all open orders; set paper.enabled: false in config.yaml to stop future runs
    0
    >>> halt("strategy_example", flatten=True)  # doctest: +SKIP
    strategy_example: cancelled open orders and sent orders to close all positions
    0
    """

    s = load_strategy(name)
    broker = make_broker(s)
    if flatten:
        broker.close_all_positions()
        print(f"{name}: cancelled open orders and sent orders to close all positions")
    else:
        broker.cancel_all()
        print(f"{name}: cancelled all open orders; set paper.enabled: false in config.yaml to stop future runs")

    return 0
