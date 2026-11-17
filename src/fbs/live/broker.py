'''
broker.py - Alpaca paper trading adapter, the only code in the repo that talks
to the Alpaca trading API.
'''

# %%
# Imports

import os
from dataclasses import dataclass
from datetime import datetime, time
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

# %%
# Constants

# Every request must go to this host, never to the live-money endpoint
PAPER_URL_FRAGMENT = "paper-api.alpaca.markets"

# Exchange time zone: sessions are New York dates
NY = ZoneInfo("America/New_York")

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
        Alpaca symbol.
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
    Summary of the paper account.

    Attributes
    ----------
    equity : float
        Account equity in USD.
    buying_power : float
        Buying power in USD.
    status : str
        Alpaca account status, e.g. "AccountStatus.ACTIVE".
    trading_blocked : bool
        True if Alpaca blocks trading.
    account_blocked : bool
        True if Alpaca blocks the account.
    """

    equity: float
    buying_power: float
    status: str
    trading_blocked: bool
    account_blocked: bool

# Trading permissions of one symbol
@dataclass(frozen=True)
class AssetInfo:
    """
    What Alpaca allows for one symbol.

    Attributes
    ----------
    tradable : bool
        Active and tradable on Alpaca.
    shortable : bool
        Alpaca allows short sales.
    easy_to_borrow : bool
        Shares are easy to borrow for a short.
    """

    tradable: bool
    shortable: bool
    easy_to_borrow: bool

# %%
# Credentials

# API keys of one paper account
def credentials(account):
    """
    API keys of one Alpaca paper account, from ALPACA_{ACCOUNT}_KEY and
    ALPACA_{ACCOUNT}_SECRET in the environment or .env.

    Parameters
    ----------
    account : str
        Account name from config.yaml paper.account.

    Returns
    -------
    key, secret : str
        API key and secret.

    Raises
    ------
    RuntimeError
        If either variable is missing.
    """

    # Read the two variables, loading .env first
    load_dotenv()
    prefix = f"ALPACA_{account.upper()}"
    key, secret = os.getenv(f"{prefix}_KEY"), os.getenv(f"{prefix}_SECRET")
    if not key or not secret:
        raise RuntimeError(f"set {prefix}_KEY and {prefix}_SECRET in the environment or .env")

    return key, secret

# %%
# Alpaca Broker

# Alpaca paper trading client
class AlpacaBroker:
    """
    Alpaca paper trading client. Construction fails for anything that is not
    a paper account. alpaca-py is imported inside the methods, so the rest of
    fbs.live works without it.

    Parameters
    ----------
    account : str
        Account name from config.yaml paper.account.
    mode : str
        Must be "paper".
    """

    def __init__(self, account, mode="paper"):
        from alpaca.data.historical import StockHistoricalDataClient
        from alpaca.trading.client import TradingClient

        # Paper only
        if mode != "paper":
            raise ValueError("AlpacaBroker only supports mode='paper'")

        # Trading client, checked to point at the paper endpoint
        key, secret = credentials(account)
        self._trading = TradingClient(key, secret, paper=True)
        base_url = getattr(self._trading._base_url, "value", self._trading._base_url)  # alpaca-py stores an enum
        if PAPER_URL_FRAGMENT not in str(base_url):
            raise RuntimeError("refusing to trade: client is not pointed at the Alpaca paper endpoint")

        # Market data client, for latest prices
        self._data = StockHistoricalDataClient(key, secret)

    # Market clock
    def clock(self):
        """
        Alpaca market clock.

        Returns
        -------
        clock : alpaca Clock
            .timestamp, .is_open, .next_open, .next_close.
        """

        clock = self._trading.get_clock()

        return clock

    # Trading sessions
    def sessions(self, start, end):
        """
        Trading sessions between two dates.

        Parameters
        ----------
        start, end : date
            First and last calendar date, inclusive.

        Returns
        -------
        sessions : list of date
            Session dates, ascending.
        """

        from alpaca.trading.requests import GetCalendarRequest

        calendar = self._trading.get_calendar(GetCalendarRequest(start=start, end=end))
        sessions = [c.date for c in calendar]

        return sessions

    # Account summary
    def account(self):
        """
        Current account summary.

        Returns
        -------
        state : AccountState
            Equity, buying power, status and block flags.
        """

        a = self._trading.get_account()
        state = AccountState(float(a.equity), float(a.buying_power), str(a.status),
                             bool(a.trading_blocked), bool(a.account_blocked))

        return state

    # Open positions
    def positions(self):
        """
        Open positions.

        Returns
        -------
        positions : dict of str to int
            Shares held per symbol, negative for shorts.
        """

        positions = {p.symbol: int(float(p.qty)) for p in self._trading.get_all_positions()}

        return positions

    # Trading permissions of one symbol
    def asset(self, symbol):
        """
        What Alpaca allows for one symbol.

        Parameters
        ----------
        symbol : str
            Alpaca symbol.

        Returns
        -------
        info : AssetInfo
            All False if Alpaca does not know the symbol.
        """

        # Unknown symbols are not tradable
        try:
            a = self._trading.get_asset(symbol)
        except Exception:
            return AssetInfo(False, False, False)

        # Tradable only while active
        active = str(a.status).lower().endswith("active")
        info = AssetInfo(bool(a.tradable) and active, bool(a.shortable), bool(a.easy_to_borrow))

        return info

    # Latest trade prices
    def latest_prices(self, symbols):
        """
        Latest trade price of each symbol.

        Parameters
        ----------
        symbols : list of str
            Alpaca symbols.

        Returns
        -------
        prices : dict of str to float
            Latest price per symbol. Symbols without a trade are left out.
        """

        from alpaca.data.requests import StockLatestTradeRequest

        if not symbols:
            return {}
        trades = self._data.get_stock_latest_trade(StockLatestTradeRequest(symbol_or_symbols=symbols))
        prices = {s: float(t.price) for s, t in trades.items()}

        return prices

    # Recent orders of one strategy
    def orders_with_prefix(self, prefix, since):
        """
        Orders whose client_order_id starts with a prefix.

        Parameters
        ----------
        prefix : str
            client_order_id prefix, e.g. "strategy_example-".
        since : datetime
            Only orders submitted after this time.

        Returns
        -------
        orders : list of alpaca Order
            Matching orders, any status, oldest first.
        """

        from alpaca.common.enums import Sort
        from alpaca.trading.enums import QueryOrderStatus
        from alpaca.trading.requests import GetOrdersRequest

        # Oldest first, 500 per page, each page after the last one's submission time
        orders, seen, after = [], set(), since
        while True:
            page = self._trading.get_orders(GetOrdersRequest(
                status=QueryOrderStatus.ALL, after=after, limit=500, direction=Sort.ASC))
            new = [o for o in page if o.id not in seen]
            seen.update(o.id for o in new)
            orders += [o for o in new if (o.client_order_id or "").startswith(prefix)]
            if len(page) < 500 or not new:
                break
            after = page[-1].submitted_at

        return orders

    # Daily account equity
    def equity_history(self, start):
        """
        Closing equity of the account on each session since a date.

        Parameters
        ----------
        start : date
            First session.

        Returns
        -------
        equity : pd.Series
            Index = session dates (Timestamp), values = equity in USD. Days
            before the account was funded are left out.
        """

        import pandas as pd
        from alpaca.trading.requests import GetPortfolioHistoryRequest

        request = GetPortfolioHistoryRequest(timeframe="1D", start=datetime.combine(start, time(), tzinfo=NY))
        h = self._trading.get_portfolio_history(request)
        days = pd.to_datetime(h.timestamp, unit="s", utc=True).tz_convert(NY).normalize().tz_localize(None)
        equity = pd.Series(h.equity, index=days, dtype=float)
        equity = equity[equity > 0]

        return equity

    # Daily closing prices
    def daily_closes(self, symbols, start, end):
        """
        Unadjusted daily closing price of each symbol, from consolidated (SIP)
        daily bars.

        Parameters
        ----------
        symbols : list of str
            Alpaca symbols.
        start, end : date
            First and last session, inclusive.

        Returns
        -------
        closes : pd.DataFrame
            Index = session dates (Timestamp), Columns = symbols.
        """

        import pandas as pd
        from alpaca.data.enums import Adjustment, DataFeed
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame

        if not symbols:
            return pd.DataFrame()
        bars = self._data.get_stock_bars(StockBarsRequest(
            symbol_or_symbols=list(symbols), timeframe=TimeFrame.Day,
            start=datetime.combine(start, time(), tzinfo=NY),
            end=datetime.combine(end, time(23, 59), tzinfo=NY),
            adjustment=Adjustment.RAW, feed=DataFeed.SIP)).df
        if bars.empty:
            return pd.DataFrame()
        bars = bars.reset_index()
        bars["day"] = pd.to_datetime(bars["timestamp"], utc=True).dt.tz_convert(NY).dt.normalize().dt.tz_localize(None)
        closes = bars.pivot(index="day", columns="symbol", values="close")

        return closes

    # Market-on-close order
    def submit_moc(self, intent):
        """
        Submit one market-on-close order.

        Parameters
        ----------
        intent : OrderIntent
            The order to send.

        Returns
        -------
        status : str
            Alpaca order status after submission.
        """

        from alpaca.trading.enums import OrderSide, TimeInForce
        from alpaca.trading.requests import MarketOrderRequest

        order = self._trading.submit_order(MarketOrderRequest(
            symbol=intent.symbol,
            qty=intent.qty,
            side=OrderSide.BUY if intent.side == "buy" else OrderSide.SELL,
            time_in_force=TimeInForce.CLS,
            client_order_id=intent.client_order_id,
        ))
        status = str(order.status)

        return status

    # Cancel open orders
    def cancel_all(self):
        """
        Cancel every open order in the account.
        """

        self._trading.cancel_orders()

    # Close all positions
    def close_all_positions(self):
        """
        Cancel open orders and close every position in the account.
        """

        self._trading.close_all_positions(cancel_orders=True)
