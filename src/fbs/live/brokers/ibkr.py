'''
ibkr.py - Interactive Brokers paper trading adapter, the only code in the repo
that talks to IBKR. Connects to a running TWS or IB Gateway with ib_async and
returns the records in base.py.

Where IBKR differs from Alpaca, and what this file does about it:
    connection  TWS / IB Gateway must be running and logged into a paper
                account (account id DU...). Every connected account must be a
                paper account, or construction fails.
    clock       No clock or calendar API: the NYSE calendar from
                exchange_calendars (base.calendar_clock, calendar_sessions).
    orders      client_order_id is sent as orderRef. IBKR does not enforce
                unique orderRefs and forgets finished orders after a few days,
                so every order sent is also kept in records/ibkr-orders.json;
                re-runs skip any client_order_id found there or at IBKR.
    equity      No portfolio history API: each connection during or after a
                session records the previous session's closing equity
                (PreviousDayEquityWithLoanValue) and, after the close, today's
                NetLiquidation, in records/ibkr-equity.csv.
    symbols     config.yaml uses Alpaca's BRK.B; IBKR writes BRK B.
'''

# %%
# Imports

import atexit
import json
import math
import os
import time as clock_time
from dataclasses import asdict, replace
from datetime import datetime, time, timedelta, timezone

from dotenv import load_dotenv

from fbs.live.brokers.base import (NY, AccountState, AssetInfo, OrderRecord, calendar_clock,
                                   calendar_sessions)

# %%
# Constants

# IBKR paper account ids start with DU (individual) or DF (advisor master)
PAPER_ACCOUNT_PREFIXES = ("DU", "DF")

# Connection defaults: IB Gateway paper port (TWS paper is 7497)
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 4002
DEFAULT_CLIENT_ID = 1
CONNECT_TIMEOUT = 15

# reqMarketDataType: 1 live only, 3 live if subscribed else 15-minute delayed
DEFAULT_MARKET_DATA_TYPE = 3

# Seconds to wait for short-availability ticks, and for an order to be acknowledged
SHORTABLE_WAIT = 2.0
ORDER_WAIT = 5.0

# Generic tick 236 sets Ticker.shortable: > 2.5 easy to borrow, > 1.5 hard to borrow
TICK_SHORTABLE = "236"
SHORTABLE_LEVEL = 1.5
EASY_TO_BORROW_LEVEL = 2.5

# Local state under strategy/{name}/records/
ORDERS_FILE = "ibkr-orders.json"
EQUITY_FILE = "ibkr-equity.csv"

# IBKR order status -> OrderRecord status (Alpaca's vocabulary)
IB_STATUS = {
    "PendingSubmit": "pending_new",
    "ApiPending": "pending_new",
    "PreSubmitted": "accepted",
    "Submitted": "new",
    "ValidationError": "accepted",   # usually corrected by IBKR and still live
    "ApiUpdate": "new",
    "PendingCancel": "pending_cancel",
    "ApiCancelled": "canceled",
    "Cancelled": "canceled",
    "Filled": "filled",
    "Inactive": "rejected",
}

# One socket per (host, port, client id) per process: IBKR refuses a second
# connection with the same client id
_CONNECTIONS = {}

# %%
# Settings

# Connection settings of one paper account
def settings(account):
    """
    Connection settings of one IBKR paper account, from the environment or
    .env:

        IBKR_{ACCOUNT}_ACCOUNT_ID        required, the paper account id DU...
        IBKR_{ACCOUNT}_HOST              default 127.0.0.1
        IBKR_{ACCOUNT}_PORT              default 4002 (IB Gateway paper)
        IBKR_{ACCOUNT}_CLIENT_ID         default 1
        IBKR_{ACCOUNT}_MARKET_DATA_TYPE  default 3

    Parameters
    ----------
    account : str
        Account name from config.yaml paper.account.

    Returns
    -------
    s : dict
        account_id, host, port, client_id, market_data_type.

    Raises
    ------
    RuntimeError
        If IBKR_{ACCOUNT}_ACCOUNT_ID is missing or is not a paper account id.

    Examples
    --------
    >>> os.environ["IBKR_DEMO_ACCOUNT_ID"] = "DU1234567"
    >>> settings("demo")
    {'account_id': 'DU1234567', 'host': '127.0.0.1', 'port': 4002, 'client_id': 1, 'market_data_type': 3}
    >>> os.environ["IBKR_DEMO_ACCOUNT_ID"] = "U1234567"
    >>> settings("demo")
    Traceback (most recent call last):
    ...
    RuntimeError: refusing to trade: IBKR_DEMO_ACCOUNT_ID=U1234567 is not a paper account (DU... or DF...)
    >>> del os.environ["IBKR_DEMO_ACCOUNT_ID"]
    """

    load_dotenv()
    prefix = f"IBKR_{account.upper()}"
    account_id = os.getenv(f"{prefix}_ACCOUNT_ID", "").strip()
    if not account_id:
        raise RuntimeError(f"set {prefix}_ACCOUNT_ID (the paper account id DU...) in the environment or .env")
    if not account_id.startswith(PAPER_ACCOUNT_PREFIXES):
        raise RuntimeError(f"refusing to trade: {prefix}_ACCOUNT_ID={account_id} is not a paper account (DU... or DF...)")

    s = {
        "account_id": account_id,
        "host": os.getenv(f"{prefix}_HOST", DEFAULT_HOST),
        "port": int(os.getenv(f"{prefix}_PORT", DEFAULT_PORT)),
        "client_id": int(os.getenv(f"{prefix}_CLIENT_ID", DEFAULT_CLIENT_ID)),
        "market_data_type": int(os.getenv(f"{prefix}_MARKET_DATA_TYPE", DEFAULT_MARKET_DATA_TYPE)),
    }

    return s

# %%
# Helpers

# config.yaml symbol -> IBKR symbol
def _ib_symbol(symbol):
    """
    IBKR spelling of a symbol: share classes use a space.

    Parameters
    ----------
    symbol : str
        Symbol as in config.yaml, e.g. "BRK.B".

    Returns
    -------
    ib : str
        e.g. "BRK B".

    Examples
    --------
    >>> _ib_symbol("BRK.B"), _ib_symbol("AAPL")
    ('BRK B', 'AAPL')
    """

    ib = symbol.replace(".", " ")

    return ib

# IBKR symbol -> config.yaml symbol
def _symbol(ib):
    """
    config.yaml spelling of an IBKR symbol.

    Parameters
    ----------
    ib : str
        IBKR symbol, e.g. "BRK B".

    Returns
    -------
    symbol : str
        e.g. "BRK.B".

    Examples
    --------
    >>> _symbol("BRK B"), _symbol("AAPL")
    ('BRK.B', 'AAPL')
    """

    symbol = ib.replace(" ", ".")

    return symbol

# A usable number or None
def _number(value):
    """
    float(value) if it is a finite number IBKR actually set, else None. IBKR
    marks unset values with NaN or the largest double.

    Parameters
    ----------
    value : float or Decimal or None
        Raw IBKR value.

    Returns
    -------
    x : float or None
        The number, or None.

    Examples
    --------
    >>> import sys
    >>> _number(586.37), _number(float("nan")), _number(sys.float_info.max), _number(None)
    (586.37, None, None, None)
    """

    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(x) or abs(x) > 1e300:
        return None

    return x

# IBKR status -> OrderRecord status
def _status(ib_status, filled, qty):
    """
    OrderRecord status of an IBKR order status.

    Parameters
    ----------
    ib_status : str
        IBKR status, e.g. "Submitted".
    filled : float
        Filled shares.
    qty : float
        Ordered shares.

    Returns
    -------
    status : str
        e.g. "new", "partially_filled", "filled".

    Examples
    --------
    >>> _status("Submitted", 0, 10), _status("Submitted", 4, 10), _status("Inactive", 0, 10)
    ('new', 'partially_filled', 'rejected')
    >>> _status("Something new", 0, 10)
    'something new'
    """

    status = IB_STATUS.get(ib_status, ib_status.lower())
    if status in ("new", "accepted") and 0 < filled < qty:
        status = "partially_filled"

    return status

# %%
# Local Order Ledger

# Read records/ibkr-orders.json
def _load_orders(path):
    """
    Orders kept in the local ledger.

    Parameters
    ----------
    path : Path or None
        records/ibkr-orders.json. None for no ledger.

    Returns
    -------
    orders : dict of str to OrderRecord
        Keyed by client_order_id. Empty if the file does not exist.

    Examples
    --------
    >>> import tempfile
    >>> from pathlib import Path
    >>> path = Path(tempfile.mkdtemp()) / ORDERS_FILE
    >>> _load_orders(path)
    {}
    >>> r = OrderRecord("demo-2024-12-31-SPY-open", "SPY", "buy", 10.0, 10.0, 586.37, "filled",
    ...                 datetime(2024, 12, 31, 15, 0, tzinfo=NY))
    >>> _save_orders(path, {r.client_order_id: r})
    >>> _load_orders(path) == {r.client_order_id: r}
    True
    """

    if path is None or not path.exists():
        return {}
    orders = {}
    for cid, row in json.loads(path.read_text()).items():
        at = row.get("submitted_at")
        orders[cid] = OrderRecord(**{**row, "submitted_at": datetime.fromisoformat(at) if at else None})

    return orders

# Write records/ibkr-orders.json
def _save_orders(path, orders):
    """
    Write the local ledger.

    Parameters
    ----------
    path : Path or None
        records/ibkr-orders.json. None for no ledger.
    orders : dict of str to OrderRecord
        Keyed by client_order_id.

    Returns
    -------
    None

    Examples
    --------
    See _load_orders.
    """

    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = {cid: {**asdict(r), "submitted_at": r.submitted_at.isoformat() if r.submitted_at else None}
            for cid, r in sorted(orders.items())}
    path.write_text(json.dumps(rows, indent=2))

# Ledger updated with what IBKR reports now
def _merge(ledger, live):
    """
    The ledger with each order IBKR still knows replaced by IBKR's view; the
    ledger's submission time is kept.

    Parameters
    ----------
    ledger : dict of str to OrderRecord
        Local ledger.
    live : dict of str to OrderRecord
        Orders IBKR reports now.

    Returns
    -------
    merged : dict of str to OrderRecord
        Keyed by client_order_id.

    Examples
    --------
    >>> sent = OrderRecord("demo-2024-12-31-SPY-open", "SPY", "buy", 10.0, 0.0, None, "accepted",
    ...                    datetime(2024, 12, 31, 15, 0, tzinfo=NY))
    >>> now = replace(sent, filled_qty=10.0, filled_avg_price=586.37, status="filled", submitted_at=None)
    >>> m = _merge({sent.client_order_id: sent}, {now.client_order_id: now})
    >>> m[sent.client_order_id].status, m[sent.client_order_id].submitted_at.hour
    ('filled', 15)
    """

    merged = dict(ledger)
    for cid, r in live.items():
        old = ledger.get(cid)
        merged[cid] = replace(r, submitted_at=(old.submitted_at if old else None) or r.submitted_at)

    return merged

# %%
# Local Equity History

# Read records/ibkr-equity.csv
def _load_equity(path):
    """
    Closing equity per session recorded so far.

    Parameters
    ----------
    path : Path or None
        records/ibkr-equity.csv. None for no file.

    Returns
    -------
    equity : pd.Series
        Index = session dates (Timestamp), values = equity in USD.

    Examples
    --------
    >>> import tempfile
    >>> import pandas as pd
    >>> from pathlib import Path
    >>> path = Path(tempfile.mkdtemp()) / EQUITY_FILE
    >>> len(_load_equity(path))
    0
    >>> _save_equity(path, pd.Series({pd.Timestamp("2024-12-31"): 100412.37,
    ...                               pd.Timestamp("2024-12-30"): 100000.0}))
    >>> _load_equity(path)
    session
    2024-12-30    100000.00
    2024-12-31    100412.37
    Name: equity, dtype: float64
    """

    import pandas as pd

    if path is None or not path.exists():
        return pd.Series(dtype=float, name="equity", index=pd.DatetimeIndex([], name="session"))
    df = pd.read_csv(path, parse_dates=["session"])
    equity = df.set_index("session")["equity"].astype(float).sort_index()

    return equity

# Write records/ibkr-equity.csv
def _save_equity(path, equity):
    """
    Write the equity history, one row per session, ascending.

    Parameters
    ----------
    path : Path or None
        records/ibkr-equity.csv. None for no file.
    equity : pd.Series
        Index = session dates (Timestamp), values = equity in USD.

    Returns
    -------
    None

    Examples
    --------
    See _load_equity.
    """

    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    out = equity.sort_index().rename("equity")
    out.index = out.index.strftime("%Y-%m-%d")
    out.rename_axis("session").to_csv(path)

# %%
# Connection

# Shared socket to TWS / IB Gateway
def _connect(s):
    """
    Connect to TWS / IB Gateway, reusing this process's open socket with the
    same host, port and client id.

    Parameters
    ----------
    s : dict
        Output of settings.

    Returns
    -------
    ib : ib_async.IB
        Connected client.

    Raises
    ------
    RuntimeError
        If the gateway is logged into a live account or not into s["account_id"].

    Examples
    --------
    Needs a running IB Gateway logged into the paper account:

    >>> ib = _connect(settings("STRATEGY_EXAMPLE"))  # doctest: +SKIP
    """

    from ib_async import IB

    key = (s["host"], s["port"], s["client_id"])
    ib = _CONNECTIONS.get(key)
    if ib is not None and ib.isConnected():
        return ib

    # Connect, then refuse anything that is not the configured paper account
    ib = IB()
    ib.connect(s["host"], s["port"], clientId=s["client_id"], timeout=CONNECT_TIMEOUT,
               account=s["account_id"])
    accounts = ib.managedAccounts()
    live = [a for a in accounts if not a.startswith(PAPER_ACCOUNT_PREFIXES)]
    if live or s["account_id"] not in accounts:
        ib.disconnect()
        raise RuntimeError(f"refusing to trade: gateway at {s['host']}:{s['port']} manages {accounts}, "
                           f"expected paper account {s['account_id']}")
    ib.reqMarketDataType(s["market_data_type"])
    _CONNECTIONS[key] = ib

    return ib

# Close every socket at exit
@atexit.register
def _disconnect_all():
    """
    Disconnect every open socket; runs at interpreter exit.

    Parameters
    ----------
    None

    Returns
    -------
    None

    Examples
    --------
    >>> _disconnect_all()
    """

    for ib in _CONNECTIONS.values():
        if ib.isConnected():
            ib.disconnect()
    _CONNECTIONS.clear()

# %%
# IBKR Broker

# IBKR paper trading client
class IBKRBroker:
    """
    IBKR paper trading client, implementing base.Broker. Construction fails
    unless the gateway is logged into the configured paper account. ib_async
    is imported inside the methods, so the rest of fbs.live works without it.

    Parameters
    ----------
    account : str
        Account name from config.yaml paper.account.
    mode : str
        Must be "paper".
    state_dir : Path or None
        Folder for ibkr-orders.json and ibkr-equity.csv, normally
        strategy/{name}/records. None keeps no local state.
    """

    def __init__(self, account, mode="paper", state_dir=None):
        """
        Connect to the gateway, sync the local order ledger and record equity.

        Parameters
        ----------
        account : str
            Account name from config.yaml paper.account.
        mode : str
            Must be "paper".
        state_dir : Path or None
            Folder for the local order ledger and equity history.

        Returns
        -------
        None

        Raises
        ------
        ValueError
            If `mode` is not "paper".
        RuntimeError
            If the settings are missing, or the gateway is not logged into
            the paper account.

        Examples
        --------
        Needs a running IB Gateway logged into the paper account:

        >>> broker = IBKRBroker("STRATEGY_EXAMPLE")  # doctest: +SKIP
        >>> IBKRBroker("STRATEGY_EXAMPLE", mode="live")
        Traceback (most recent call last):
        ...
        ValueError: IBKRBroker only supports mode='paper'
        """

        # Paper only
        if mode != "paper":
            raise ValueError("IBKRBroker only supports mode='paper'")

        s = settings(account)
        self._account = s["account_id"]
        self._ib = _connect(s)
        self._contracts = {}
        self._orders_path = state_dir / ORDERS_FILE if state_dir is not None else None
        self._equity_path = state_dir / EQUITY_FILE if state_dir is not None else None

        # Bring the local state up to date while IBKR still remembers
        self._sync_orders(None)
        self._record_equity()

    # Market clock
    def clock(self):
        """
        Market clock at the gateway's time, from the NYSE calendar.

        Parameters
        ----------
        None

        Returns
        -------
        clock : MarketClock
            .timestamp, .is_open, .next_open, .next_close.

        Examples
        --------
        >>> broker = IBKRBroker("STRATEGY_EXAMPLE")  # doctest: +SKIP
        >>> broker.clock().is_open  # doctest: +SKIP
        False
        """

        now = self._ib.reqCurrentTime()
        now = (now if now.tzinfo else now.replace(tzinfo=timezone.utc)).astimezone(NY)
        clock = calendar_clock(now)

        return clock

    # Trading sessions
    def sessions(self, start, end):
        """
        NYSE trading sessions between two dates.

        Parameters
        ----------
        start, end : date
            First and last calendar date, inclusive.

        Returns
        -------
        sessions : list of date
            Session dates, ascending.

        Examples
        --------
        >>> from datetime import date
        >>> broker = IBKRBroker("STRATEGY_EXAMPLE")  # doctest: +SKIP
        >>> broker.sessions(date(2024, 12, 23), date(2024, 12, 27))  # doctest: +SKIP
        [datetime.date(2024, 12, 23), datetime.date(2024, 12, 24), datetime.date(2024, 12, 26), datetime.date(2024, 12, 27)]
        """

        sessions = calendar_sessions(start, end)

        return sessions

    # Account summary
    def account(self):
        """
        Current account summary. IBKR has no account status or block flags
        in the API: a connected paper account counts as active.

        Parameters
        ----------
        None

        Returns
        -------
        state : AccountState
            NetLiquidation as equity, BuyingPower as buying power.

        Examples
        --------
        >>> broker = IBKRBroker("STRATEGY_EXAMPLE")  # doctest: +SKIP
        >>> broker.account()  # doctest: +SKIP
        AccountState(equity=1000000.0, buying_power=4000000.0, active=True, trading_blocked=False, account_blocked=False, status='DU1234567 connected')
        """

        s = self._summary()
        state = AccountState(s.get("NetLiquidation", 0.0), s.get("BuyingPower", 0.0), True, False, False,
                             f"{self._account} connected")

        return state

    # Open positions
    def positions(self):
        """
        Open stock positions.

        Parameters
        ----------
        None

        Returns
        -------
        positions : dict of str to int
            Shares held per symbol, negative for shorts.

        Examples
        --------
        >>> broker = IBKRBroker("STRATEGY_EXAMPLE")  # doctest: +SKIP
        >>> broker.positions()  # doctest: +SKIP
        {'QQQ': 125, 'SPY': 100}
        """

        positions = {_symbol(p.contract.symbol): int(p.position) for p in self._ib.positions(self._account)
                     if p.contract.secType == "STK" and p.position}

        return positions

    # Trading permissions of each symbol
    def assets(self, symbols):
        """
        What IBKR allows for each symbol: tradable if IBKR knows the US stock,
        shortable and easy to borrow from the short-availability tick (236).

        Parameters
        ----------
        symbols : list of str
            Symbols as in config.yaml.

        Returns
        -------
        assets : dict of str to AssetInfo
            All False for a symbol IBKR does not know.

        Examples
        --------
        >>> broker = IBKRBroker("STRATEGY_EXAMPLE")  # doctest: +SKIP
        >>> broker.assets(["SPY", "NOT_A_SYMBOL"])  # doctest: +SKIP
        {'SPY': AssetInfo(tradable=True, shortable=True, easy_to_borrow=True), 'NOT_A_SYMBOL': AssetInfo(tradable=False, shortable=False, easy_to_borrow=False)}
        """

        # Short availability of every known symbol, streamed for a moment
        contracts = self._qualified(symbols)
        tickers = {sym: self._ib.reqMktData(c, TICK_SHORTABLE) for sym, c in contracts.items()}
        if tickers:
            self._ib.sleep(SHORTABLE_WAIT)

        assets = {}
        for sym in symbols:
            if sym not in contracts:
                assets[sym] = AssetInfo(False, False, False)
                continue
            level = _number(tickers[sym].shortable) or 0.0
            self._ib.cancelMktData(contracts[sym])
            assets[sym] = AssetInfo(True, level > SHORTABLE_LEVEL, level > EASY_TO_BORROW_LEVEL)

        return assets

    # Latest prices
    def latest_prices(self, symbols):
        """
        Latest trade price of each symbol (live or 15-minute delayed,
        depending on the market data subscription); the midpoint or the last
        close if there is no trade.

        Parameters
        ----------
        symbols : list of str
            Symbols as in config.yaml.

        Returns
        -------
        prices : dict of str to float
            Latest price per symbol. Symbols without a price are left out.

        Examples
        --------
        >>> broker = IBKRBroker("STRATEGY_EXAMPLE")  # doctest: +SKIP
        >>> broker.latest_prices(["SPY", "QQQ"])  # doctest: +SKIP
        {'SPY': 591.15, 'QQQ': 515.29}
        """

        contracts = self._qualified(symbols)
        if not contracts:
            return {}
        tickers = {t.contract.conId: t for t in self._ib.reqTickers(*contracts.values())}

        prices = {}
        for sym, c in contracts.items():
            t = tickers.get(c.conId)
            if t is None:
                continue
            for p in (t.last, t.marketPrice(), t.close):
                p = _number(p)
                if p and p > 0:
                    prices[sym] = p
                    break

        return prices

    # Recent orders of one strategy
    def orders_with_prefix(self, prefix, since):
        """
        Orders whose client_order_id starts with a prefix, from the local
        ledger updated with what IBKR reports now.

        Parameters
        ----------
        prefix : str
            client_order_id prefix, e.g. "strategy_example-".
        since : datetime
            Only orders submitted after this time.

        Returns
        -------
        orders : list of OrderRecord
            Matching orders, any status, oldest first.

        Examples
        --------
        >>> broker = IBKRBroker("STRATEGY_EXAMPLE")  # doctest: +SKIP
        >>> orders = broker.orders_with_prefix(
        ...     "strategy_example-", datetime(2024, 12, 1, tzinfo=NY))  # doctest: +SKIP
        >>> [o.client_order_id for o in orders]  # doctest: +SKIP
        ['strategy_example-2024-12-31-SPY-adjust']
        """

        ledger = self._sync_orders(prefix)
        orders = [r for cid, r in ledger.items()
                  if cid.startswith(prefix) and (r.submitted_at is None or r.submitted_at >= since)]
        orders.sort(key=lambda r: r.submitted_at or since)

        return orders

    # Daily account equity
    def equity_history(self, start):
        """
        Closing equity of the account on each session since a date, from
        records/ibkr-equity.csv. Only sessions on which (or the day after
        which) the broker connected are present.

        Parameters
        ----------
        start : date
            First session.

        Returns
        -------
        equity : pd.Series
            Index = session dates (Timestamp), values = equity in USD.

        Examples
        --------
        >>> from datetime import date
        >>> broker = IBKRBroker("STRATEGY_EXAMPLE")  # doctest: +SKIP
        >>> broker.equity_history(date(2024, 12, 30))  # doctest: +SKIP
        session
        2024-12-30    100000.00
        2024-12-31    100412.37
        Name: equity, dtype: float64
        """

        import pandas as pd

        equity = _load_equity(self._equity_path)
        equity = equity[(equity.index >= pd.Timestamp(start)) & (equity > 0)]

        return equity

    # Daily closing prices
    def daily_closes(self, symbols, start, end):
        """
        Daily closing price of each symbol, from IBKR TRADES daily bars
        (split-adjusted, not dividend-adjusted).

        Parameters
        ----------
        symbols : list of str
            Symbols as in config.yaml.
        start, end : date
            First and last session, inclusive.

        Returns
        -------
        closes : pd.DataFrame
            Index = session dates (Timestamp), Columns = symbols.

        Examples
        --------
        >>> from datetime import date
        >>> broker = IBKRBroker("STRATEGY_EXAMPLE")  # doctest: +SKIP
        >>> broker.daily_closes(["SPY", "QQQ"], date(2024, 12, 30),
        ...                     date(2024, 12, 31))  # doctest: +SKIP
        symbol         QQQ     SPY
        day
        2024-12-30  515.61  588.22
        2024-12-31  511.23  586.08
        """

        import pandas as pd

        contracts = self._qualified(symbols)
        if not contracts:
            return pd.DataFrame()

        # One request per symbol, ending the day after `end`
        days = (end - start).days + 1
        duration = f"{days} D" if days <= 365 else f"{math.ceil(days / 365)} Y"
        end_at = datetime.combine(end + timedelta(days=1), time(), tzinfo=NY)
        columns = {}
        for sym, c in contracts.items():
            bars = self._ib.reqHistoricalData(c, endDateTime=end_at, durationStr=duration,
                                              barSizeSetting="1 day", whatToShow="TRADES", useRTH=True)
            columns[sym] = pd.Series({pd.Timestamp(b.date): float(b.close) for b in bars}, dtype=float)

        closes = pd.DataFrame(columns)
        closes = closes[(closes.index >= pd.Timestamp(start)) & (closes.index <= pd.Timestamp(end))]
        closes.index.name, closes.columns.name = "day", "symbol"

        return closes

    # Market-on-close order
    def submit_moc(self, intent):
        """
        Submit one market-on-close order, with client_order_id as orderRef.
        The order goes into the local ledger before it is sent, so a crash
        after sending never leads to a second send.

        Parameters
        ----------
        intent : OrderIntent
            The order to send.

        Returns
        -------
        status : str
            Order status after IBKR acknowledges it, e.g. "accepted".

        Raises
        ------
        ValueError
            If IBKR does not know the symbol.
        RuntimeError
            If IBKR rejects or cancels the order.

        Examples
        --------
        >>> from fbs.live.brokers.base import OrderIntent
        >>> broker = IBKRBroker("STRATEGY_EXAMPLE")  # doctest: +SKIP
        >>> intent = OrderIntent("SPY", "buy", 10,
        ...                      "strategy_example-2024-12-31-SPY-open", 0.06, "open")
        >>> broker.submit_moc(intent)  # doctest: +SKIP
        'accepted'
        """

        from ib_async import Order

        contract = self._qualified([intent.symbol]).get(intent.symbol)
        if contract is None:
            raise ValueError(f"{intent.symbol} is not a US stock IBKR knows")

        # Ledger first
        pending = OrderRecord(intent.client_order_id, intent.symbol, intent.side, float(intent.qty), 0.0, None,
                              "pending_new", datetime.now(NY))
        self._put(pending)

        # Send; a send that fails outright leaves nothing at IBKR, so drop it from the ledger
        order = Order(action="BUY" if intent.side == "buy" else "SELL", totalQuantity=intent.qty,
                      orderType="MOC", tif="DAY", orderRef=intent.client_order_id, account=self._account)
        try:
            trade = self._ib.placeOrder(contract, order)
        except Exception:
            self._drop(intent.client_order_id)
            raise

        # Wait for IBKR to acknowledge it
        deadline = clock_time.monotonic() + ORDER_WAIT
        while trade.orderStatus.status in ("", "PendingSubmit", "ApiPending") and clock_time.monotonic() < deadline:
            self._ib.sleep(0.2)
        status = _status(trade.orderStatus.status, trade.orderStatus.filled, intent.qty)
        self._put(replace(pending, status=status))
        if status in ("rejected", "canceled"):
            errors = "; ".join(f"{e.errorCode} {e.message}" for e in trade.log if e.errorCode)
            raise RuntimeError(errors or trade.orderStatus.status)

        return status

    # Cancel open orders
    def cancel_all(self):
        """
        Cancel every open order in the account (IBKR global cancel).

        Parameters
        ----------
        None

        Returns
        -------
        None

        Examples
        --------
        >>> broker = IBKRBroker("STRATEGY_EXAMPLE")  # doctest: +SKIP
        >>> broker.cancel_all()  # doctest: +SKIP
        """

        self._ib.reqGlobalCancel()
        self._ib.sleep(1)

    # Close all positions
    def close_all_positions(self):
        """
        Cancel open orders and send a market order closing every stock
        position. Outside the regular session the orders wait for the open.

        Parameters
        ----------
        None

        Returns
        -------
        None

        Examples
        --------
        >>> broker = IBKRBroker("STRATEGY_EXAMPLE")  # doctest: +SKIP
        >>> broker.close_all_positions()  # doctest: +SKIP
        """

        from ib_async import MarketOrder

        self.cancel_all()
        today = datetime.now(NY).date().isoformat()
        positions = self.positions()
        contracts = self._qualified(list(positions))
        for sym, qty in positions.items():
            if sym not in contracts:
                print(f"  {sym}: IBKR cannot resolve the contract; close it in TWS")
                continue
            order = MarketOrder("SELL" if qty > 0 else "BUY", abs(qty), tif="DAY", account=self._account,
                                orderRef=f"flatten-{today}-{sym}")
            self._ib.placeOrder(contracts[sym], order)
        self._ib.sleep(1)

    # Release the connection
    def close(self):
        """
        Disconnect from the gateway.

        Parameters
        ----------
        None

        Returns
        -------
        None

        Examples
        --------
        >>> broker = IBKRBroker("STRATEGY_EXAMPLE")  # doctest: +SKIP
        >>> broker.close()  # doctest: +SKIP
        """

        for key, ib in list(_CONNECTIONS.items()):
            if ib is self._ib:
                ib.disconnect()
                del _CONNECTIONS[key]

    # Qualified stock contracts
    def _qualified(self, symbols):
        """
        IBKR contract of each symbol IBKR knows (US stock, SMART routing),
        cached for the life of the broker.

        Parameters
        ----------
        symbols : list of str
            Symbols as in config.yaml.

        Returns
        -------
        contracts : dict of str to Contract
            Symbols IBKR does not know are left out.
        """

        from ib_async import Stock

        missing = [s for s in symbols if s not in self._contracts]
        if missing:
            contracts = [Stock(_ib_symbol(s), "SMART", "USD") for s in missing]
            self._ib.qualifyContracts(*contracts)   # fills conId in place; unknown ones keep 0
            for s, c in zip(missing, contracts):
                self._contracts[s] = c if c.conId else None
        contracts = {s: self._contracts[s] for s in symbols if self._contracts.get(s) is not None}

        return contracts

    # Account summary values in USD
    def _summary(self):
        """
        Numeric account summary values of the account, in USD.

        Parameters
        ----------
        None

        Returns
        -------
        values : dict of str to float
            e.g. NetLiquidation, BuyingPower, PreviousDayEquityWithLoanValue.
        """

        values = {}
        for v in self._ib.accountSummary(self._account):
            x = _number(v.value)
            if v.account == self._account and v.currency in ("USD", "BASE") and x is not None:
                values.setdefault(v.tag, x)

        return values

    # Orders IBKR reports now
    def _live_orders(self):
        """
        Every order of the account with an orderRef that IBKR reports this
        session (open and recently completed), with fills from the
        executions.

        Parameters
        ----------
        None

        Returns
        -------
        orders : dict of str to OrderRecord
            Keyed by client_order_id (= orderRef).
        """

        # Filled shares and notional per orderRef, from the executions
        fills = {}
        for f in self._ib.fills():
            ex = f.execution
            if not ex.orderRef or (ex.acctNumber and ex.acctNumber != self._account):
                continue
            shares, notional = fills.get(ex.orderRef, (0.0, 0.0))
            fills[ex.orderRef] = (shares + float(ex.shares), notional + float(ex.shares) * float(ex.price))

        orders = {}
        for t in self._ib.trades():
            o, st = t.order, t.orderStatus
            ref = o.orderRef or ""
            if not ref or (o.account and o.account != self._account):
                continue
            qty = _number(o.totalQuantity) or 0.0
            filled = max(_number(st.filled) or 0.0, _number(o.filledQuantity) or 0.0)
            avg = _number(st.avgFillPrice) or None
            shares, notional = fills.get(ref, (0.0, 0.0))
            if shares:
                filled, avg = max(filled, shares), notional / shares
            orders[ref] = OrderRecord(
                client_order_id=ref, symbol=_symbol(t.contract.symbol),
                side="buy" if o.action == "BUY" else "sell", qty=qty, filled_qty=filled,
                filled_avg_price=avg if filled else None, status=_status(st.status, filled, qty),
                submitted_at=t.log[0].time if t.log else None,
            )

        return orders

    # Ledger updated from IBKR
    def _sync_orders(self, prefix):
        """
        Update the local ledger with what IBKR reports now and save it.

        Parameters
        ----------
        prefix : str or None
            Also add IBKR orders whose orderRef starts with this prefix. None
            only updates orders already in the ledger.

        Returns
        -------
        ledger : dict of str to OrderRecord
            The updated ledger; just IBKR's orders if there is no state_dir.
        """

        ledger = _load_orders(self._orders_path)
        live = {cid: r for cid, r in self._live_orders().items()
                if cid in ledger or (prefix is not None and cid.startswith(prefix))}
        ledger = _merge(ledger, live)
        _save_orders(self._orders_path, ledger)

        return ledger

    # Add or replace one ledger entry
    def _put(self, record):
        """
        Add or replace one order in the local ledger.

        Parameters
        ----------
        record : OrderRecord
            The order.

        Returns
        -------
        None
        """

        ledger = _load_orders(self._orders_path)
        ledger[record.client_order_id] = record
        _save_orders(self._orders_path, ledger)

    # Remove one ledger entry
    def _drop(self, client_order_id):
        """
        Remove one order from the local ledger.

        Parameters
        ----------
        client_order_id : str
            The order's id.

        Returns
        -------
        None
        """

        ledger = _load_orders(self._orders_path)
        ledger.pop(client_order_id, None)
        _save_orders(self._orders_path, ledger)

    # Record closing equity
    def _record_equity(self):
        """
        On a session day, during or after the session: record the previous
        session's closing equity (PreviousDayEquityWithLoanValue) and, after
        the close, today's NetLiquidation, in records/ibkr-equity.csv.

        Parameters
        ----------
        None

        Returns
        -------
        None
        """

        import pandas as pd

        if self._equity_path is None:
            return
        clock = self.clock()
        now = clock.timestamp.astimezone(NY)
        today = now.date()
        sessions = self.sessions(today - timedelta(days=10), today)
        done_today = not clock.is_open and clock.next_open.astimezone(NY).date() > today
        if today not in sessions or not (clock.is_open or done_today):
            return

        values = self._summary()
        equity = _load_equity(self._equity_path)
        previous = max(d for d in sessions if d < today)
        if values.get("PreviousDayEquityWithLoanValue", 0) > 0:
            equity.loc[pd.Timestamp(previous)] = values["PreviousDayEquityWithLoanValue"]
        if done_today and values.get("NetLiquidation", 0) > 0 and pd.Timestamp(today) not in equity.index:
            equity.loc[pd.Timestamp(today)] = values["NetLiquidation"]
        _save_equity(self._equity_path, equity)
