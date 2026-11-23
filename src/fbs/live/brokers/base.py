'''
base.py - What every broker adapter returns and must implement. runner.py,
fbs.execution and fbs.risk only use these records and the Broker methods, so
they work with any broker in fbs.live.brokers.
'''

# %%
# Imports

from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol
from zoneinfo import ZoneInfo

# %%
# Constants

# Exchange time zone: sessions are New York dates
NY = ZoneInfo("America/New_York")

# Exchange calendar for brokers without a clock or calendar API
CALENDAR = "XNYS"

# %%
# Records

# One planned order
@dataclass(frozen=True)
class OrderIntent:
    """
    One planned whole-share order.

    Attributes
    ----------
    symbol : str
        Symbol as written in config.yaml universe, e.g. "BRK.B".
    side : {"buy", "sell"}
        Order side.
    qty : int
        Whole shares, > 0.
    client_order_id : str
        {strategy}-{exec_session}-{symbol}-{reason}, the same on every re-run
        for the same session, so an order is never sent twice.
    target_weight : float
        Target fraction of capital for the symbol.
    reason : {"open", "close", "adjust"}
        Why the order exists.
    """

    symbol: str
    side: str
    qty: int
    client_order_id: str
    target_weight: float
    reason: str

# Account summary
@dataclass(frozen=True)
class AccountState:
    """
    Summary of the account.

    Attributes
    ----------
    equity : float
        Account equity in USD.
    buying_power : float
        Buying power in USD.
    active : bool
        True if the broker reports the account as open and active.
    trading_blocked : bool
        True if the broker blocks trading.
    account_blocked : bool
        True if the broker blocks the account.
    status : str
        The broker's own status text, for display only, e.g. "ACTIVE".
    """

    equity: float
    buying_power: float
    active: bool
    trading_blocked: bool
    account_blocked: bool
    status: str = ""

# Trading permissions of one symbol
@dataclass(frozen=True)
class AssetInfo:
    """
    What the broker allows for one symbol.

    Attributes
    ----------
    tradable : bool
        Active and tradable at the broker.
    shortable : bool
        The broker allows short sales.
    easy_to_borrow : bool
        Shares are easy to borrow for a short.
    """

    tradable: bool
    shortable: bool
    easy_to_borrow: bool

# Market clock
@dataclass(frozen=True)
class MarketClock:
    """
    Market clock at one moment.

    Attributes
    ----------
    timestamp : datetime
        Now, time zone aware.
    is_open : bool
        True during the regular session.
    next_open : datetime
        Next regular-session open.
    next_close : datetime
        Close of the current session if open, else of the next session.
    """

    timestamp: datetime
    is_open: bool
    next_open: datetime
    next_close: datetime

# One sent order and its fills
@dataclass(frozen=True)
class OrderRecord:
    """
    One order sent to the broker, any status.

    Attributes
    ----------
    client_order_id : str
        The OrderIntent's client_order_id.
    symbol : str
        Symbol as written in config.yaml universe.
    side : {"buy", "sell"}
        Order side.
    qty : float
        Ordered shares.
    filled_qty : float
        Filled shares so far.
    filled_avg_price : float or None
        Average fill price, None if nothing is filled.
    status : str
        Lower-case status in Alpaca's vocabulary: "pending_new", "accepted",
        "new", "partially_filled", "filled", "pending_cancel", "canceled",
        "expired", "rejected", ...
    submitted_at : datetime or None
        When the order was sent, time zone aware.
    """

    client_order_id: str
    symbol: str
    side: str
    qty: float
    filled_qty: float
    filled_avg_price: float | None
    status: str
    submitted_at: datetime | None

# %%
# Broker Interface

# Methods runner.py calls on a broker
class Broker(Protocol):
    """
    What runner.py needs from a broker. AlpacaBroker and IBKRBroker implement
    it; see either one for the full docstrings.
    """

    def clock(self) -> MarketClock:
        """Market clock now."""

    def sessions(self, start: date, end: date) -> list[date]:
        """Trading sessions from start to end, inclusive, ascending."""

    def account(self) -> AccountState:
        """Current account summary."""

    def positions(self) -> dict[str, int]:
        """Shares held per symbol, negative for shorts."""

    def assets(self, symbols: list[str]) -> dict[str, AssetInfo]:
        """Trading permissions of each symbol; all False if unknown."""

    def latest_prices(self, symbols: list[str]) -> dict[str, float]:
        """Latest price per symbol; symbols without a price are left out."""

    def orders_with_prefix(self, prefix: str, since: datetime) -> list[OrderRecord]:
        """Orders whose client_order_id starts with prefix, sent after since, oldest first."""

    def equity_history(self, start: date):
        """Closing account equity per session since start, as a pd.Series."""

    def daily_closes(self, symbols: list[str], start: date, end: date):
        """Daily closing price per session and symbol, as a pd.DataFrame."""

    def submit_moc(self, intent: OrderIntent) -> str:
        """Send one market-on-close order; returns its OrderRecord-style status."""

    def cancel_all(self) -> None:
        """Cancel every open order in the account."""

    def close_all_positions(self) -> None:
        """Cancel open orders and close every position in the account."""

    def close(self) -> None:
        """Release the connection, if any."""

# %%
# Calendar Helpers

# Market clock from the exchange calendar
def calendar_clock(now):
    """
    Market clock from the NYSE calendar, for brokers without a clock API.
    Holidays and early closes follow exchange_calendars.

    Parameters
    ----------
    now : datetime
        Time zone aware time.

    Returns
    -------
    clock : MarketClock
        Clock at `now`.

    Examples
    --------
    Christmas Eve 2024 closes at 13:00:

    >>> c = calendar_clock(datetime(2024, 12, 24, 10, 0, tzinfo=NY))
    >>> c.is_open, c.next_close.astimezone(NY).strftime("%Y-%m-%d %H:%M")
    (True, '2024-12-24 13:00')
    >>> c = calendar_clock(datetime(2024, 12, 24, 15, 0, tzinfo=NY))
    >>> c.is_open, c.next_open.astimezone(NY).strftime("%Y-%m-%d %H:%M")
    (False, '2024-12-26 09:30')
    """

    import exchange_calendars as xcals
    import pandas as pd

    cal = xcals.get_calendar(CALENDAR)
    ts = pd.Timestamp(now).tz_convert("UTC").floor("min")
    clock = MarketClock(timestamp=now, is_open=bool(cal.is_open_on_minute(ts)),
                        next_open=cal.next_open(ts).to_pydatetime(),
                        next_close=cal.next_close(ts).to_pydatetime())

    return clock

# Trading sessions from the exchange calendar
def calendar_sessions(start, end):
    """
    NYSE trading sessions between two dates, for brokers without a calendar
    API.

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
    >>> calendar_sessions(date(2024, 12, 23), date(2024, 12, 27))
    [datetime.date(2024, 12, 23), datetime.date(2024, 12, 24), datetime.date(2024, 12, 26), datetime.date(2024, 12, 27)]
    """

    import exchange_calendars as xcals

    sessions = xcals.get_calendar(CALENDAR).sessions_in_range(start, end).date.tolist()

    return sessions
