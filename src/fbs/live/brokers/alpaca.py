'''
alpaca.py - Alpaca paper trading adapter, the only code in the repo that talks
to the Alpaca trading API. Returns the records in base.py.
'''

# %%
# Imports

import os
from datetime import datetime, time

from dotenv import load_dotenv

from fbs.live.brokers.base import NY, AccountState, AssetInfo, MarketClock, OrderRecord

# %%
# Constants

# Every request must go to this host, never to the live-money endpoint
PAPER_URL_FRAGMENT = "paper-api.alpaca.markets"

# %%
# Helpers

# Enum value as plain text
def _text(value):
    """
    alpaca-py enum value as lower-case text; plain strings pass through.

    Parameters
    ----------
    value : Enum or str or None
        e.g. OrderStatus.FILLED.

    Returns
    -------
    text : str
        e.g. "filled".

    Examples
    --------
    >>> from enum import Enum
    >>> _text(Enum("OrderStatus", {"FILLED": "filled"}).FILLED), _text("ACTIVE"), _text(None)
    ('filled', 'active', '')
    """

    text = str(getattr(value, "value", value) or "").lower()

    return text

# Neutral record of one Alpaca order
def _order_record(o):
    """
    OrderRecord of one alpaca-py Order.

    Parameters
    ----------
    o : alpaca Order
        Order as returned by get_orders.

    Returns
    -------
    record : OrderRecord
        Same order in the broker-neutral record.

    Examples
    --------
    >>> from types import SimpleNamespace as Order
    >>> _order_record(Order(client_order_id="demo-2024-12-31-SPY-open", symbol="SPY", side="buy",
    ...                     qty="10", filled_qty="10", filled_avg_price="586.37", status="filled",
    ...                     submitted_at=None))
    OrderRecord(client_order_id='demo-2024-12-31-SPY-open', symbol='SPY', side='buy', qty=10.0, filled_qty=10.0, filled_avg_price=586.37, status='filled', submitted_at=None)
    """

    record = OrderRecord(
        client_order_id=o.client_order_id or "", symbol=o.symbol, side=_text(o.side),
        qty=float(o.qty or 0), filled_qty=float(o.filled_qty or 0),
        filled_avg_price=float(o.filled_avg_price) if o.filled_avg_price else None,
        status=_text(o.status), submitted_at=o.submitted_at,
    )

    return record

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

    Examples
    --------
    Reads the keys of config.yaml paper.account STRATEGY_EXAMPLE:

    >>> key, secret = credentials("STRATEGY_EXAMPLE")  # doctest: +SKIP
    >>> credentials("no_such_account")  # doctest: +SKIP
    Traceback (most recent call last):
    ...
    RuntimeError: set ALPACA_NO_SUCH_ACCOUNT_KEY and ALPACA_NO_SUCH_ACCOUNT_SECRET ...
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
    Alpaca paper trading client, implementing base.Broker. Construction fails
    for anything that is not a paper account. alpaca-py is imported inside the
    methods, so the rest of fbs.live works without it.

    Parameters
    ----------
    account : str
        Account name from config.yaml paper.account.
    mode : str
        Must be "paper".
    """

    def __init__(self, account, mode="paper"):
        """
        Connect the trading and market data clients of one paper account.

        Parameters
        ----------
        account : str
            Account name from config.yaml paper.account.
        mode : str
            Must be "paper".

        Returns
        -------
        None

        Raises
        ------
        ValueError
            If `mode` is not "paper".
        RuntimeError
            If the API keys are missing, or the client does not point at the
            Alpaca paper endpoint.

        Examples
        --------
        Needs the account's API keys and calls Alpaca:

        >>> broker = AlpacaBroker("STRATEGY_EXAMPLE")  # doctest: +SKIP
        >>> AlpacaBroker("STRATEGY_EXAMPLE", mode="live")  # doctest: +SKIP
        Traceback (most recent call last):
        ...
        ValueError: AlpacaBroker only supports mode='paper'
        """
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

        Parameters
        ----------
        None

        Returns
        -------
        clock : MarketClock
            .timestamp, .is_open, .next_open, .next_close.

        Examples
        --------
        >>> broker = AlpacaBroker("STRATEGY_EXAMPLE")  # doctest: +SKIP
        >>> broker.clock().is_open  # doctest: +SKIP
        False
        """

        c = self._trading.get_clock()
        clock = MarketClock(c.timestamp, bool(c.is_open), c.next_open, c.next_close)

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

        Examples
        --------
        >>> from datetime import date
        >>> broker = AlpacaBroker("STRATEGY_EXAMPLE")  # doctest: +SKIP
        >>> broker.sessions(date(2024, 12, 23), date(2024, 12, 27))  # doctest: +SKIP
        [datetime.date(2024, 12, 23), datetime.date(2024, 12, 24), datetime.date(2024, 12, 26), datetime.date(2024, 12, 27)]
        """

        from alpaca.trading.requests import GetCalendarRequest

        calendar = self._trading.get_calendar(GetCalendarRequest(start=start, end=end))
        sessions = [c.date for c in calendar]

        return sessions

    # Account summary
    def account(self):
        """
        Current account summary.

        Parameters
        ----------
        None

        Returns
        -------
        state : AccountState
            Equity, buying power, active flag, block flags and Alpaca status.

        Examples
        --------
        >>> broker = AlpacaBroker("STRATEGY_EXAMPLE")  # doctest: +SKIP
        >>> broker.account()  # doctest: +SKIP
        AccountState(equity=100000.0, buying_power=200000.0, active=True, trading_blocked=False, account_blocked=False, status='ACTIVE')
        """

        a = self._trading.get_account()
        status = _text(a.status).upper()
        state = AccountState(float(a.equity), float(a.buying_power), status == "ACTIVE",
                             bool(a.trading_blocked), bool(a.account_blocked), status)

        return state

    # Open positions
    def positions(self):
        """
        Open positions.

        Parameters
        ----------
        None

        Returns
        -------
        positions : dict of str to int
            Shares held per symbol, negative for shorts.

        Examples
        --------
        >>> broker = AlpacaBroker("STRATEGY_EXAMPLE")  # doctest: +SKIP
        >>> broker.positions()  # doctest: +SKIP
        {'QQQ': 125, 'SPY': 100}
        """

        positions = {p.symbol: int(float(p.qty)) for p in self._trading.get_all_positions()}

        return positions

    # Trading permissions of each symbol
    def assets(self, symbols):
        """
        What Alpaca allows for each symbol.

        Parameters
        ----------
        symbols : list of str
            Alpaca symbols.

        Returns
        -------
        assets : dict of str to AssetInfo
            All False for a symbol Alpaca does not know.

        Examples
        --------
        >>> broker = AlpacaBroker("STRATEGY_EXAMPLE")  # doctest: +SKIP
        >>> broker.assets(["SPY", "NOT_A_SYMBOL"])  # doctest: +SKIP
        {'SPY': AssetInfo(tradable=True, shortable=True, easy_to_borrow=True), 'NOT_A_SYMBOL': AssetInfo(tradable=False, shortable=False, easy_to_borrow=False)}
        """

        assets = {}
        for symbol in symbols:

            # Unknown symbols are not tradable
            try:
                a = self._trading.get_asset(symbol)
            except Exception:
                assets[symbol] = AssetInfo(False, False, False)
                continue

            # Tradable only while active
            active = _text(a.status).endswith("active")
            assets[symbol] = AssetInfo(bool(a.tradable) and active, bool(a.shortable), bool(a.easy_to_borrow))

        return assets

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

        Examples
        --------
        >>> broker = AlpacaBroker("STRATEGY_EXAMPLE")  # doctest: +SKIP
        >>> broker.latest_prices(["SPY", "QQQ"])  # doctest: +SKIP
        {'SPY': 591.15, 'QQQ': 515.29}
        >>> broker.latest_prices([])  # doctest: +SKIP
        {}
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
        orders : list of OrderRecord
            Matching orders, any status, oldest first.

        Examples
        --------
        >>> broker = AlpacaBroker("STRATEGY_EXAMPLE")  # doctest: +SKIP
        >>> orders = broker.orders_with_prefix(
        ...     "strategy_example-", datetime(2024, 12, 1, tzinfo=NY))  # doctest: +SKIP
        >>> [o.client_order_id for o in orders]  # doctest: +SKIP
        ['strategy_example-2024-12-31-SPY-adjust']
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
            orders += [_order_record(o) for o in new if (o.client_order_id or "").startswith(prefix)]
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

        Examples
        --------
        >>> from datetime import date
        >>> broker = AlpacaBroker("STRATEGY_EXAMPLE")  # doctest: +SKIP
        >>> broker.equity_history(date(2024, 12, 30))  # doctest: +SKIP
        2024-12-30    100000.00
        2024-12-31    100412.37
        dtype: float64
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

        Examples
        --------
        >>> from datetime import date
        >>> broker = AlpacaBroker("STRATEGY_EXAMPLE")  # doctest: +SKIP
        >>> broker.daily_closes(["SPY", "QQQ"], date(2024, 12, 30),
        ...                     date(2024, 12, 31))  # doctest: +SKIP
        symbol         QQQ     SPY
        day
        2024-12-30  515.61  588.22
        2024-12-31  511.23  586.08
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
            Alpaca order status after submission, e.g. "accepted".

        Examples
        --------
        >>> from fbs.live.brokers.base import OrderIntent
        >>> broker = AlpacaBroker("STRATEGY_EXAMPLE")  # doctest: +SKIP
        >>> intent = OrderIntent("SPY", "buy", 10,
        ...                      "strategy_example-2024-12-31-SPY-open", 0.06, "open")
        >>> broker.submit_moc(intent)  # doctest: +SKIP
        'accepted'
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
        status = _text(order.status)

        return status

    # Cancel open orders
    def cancel_all(self):
        """
        Cancel every open order in the account.

        Parameters
        ----------
        None

        Returns
        -------
        None

        Examples
        --------
        >>> broker = AlpacaBroker("STRATEGY_EXAMPLE")  # doctest: +SKIP
        >>> broker.cancel_all()  # doctest: +SKIP
        """

        self._trading.cancel_orders()

    # Close all positions
    def close_all_positions(self):
        """
        Cancel open orders and close every position in the account.

        Parameters
        ----------
        None

        Returns
        -------
        None

        Examples
        --------
        >>> broker = AlpacaBroker("STRATEGY_EXAMPLE")  # doctest: +SKIP
        >>> broker.close_all_positions()  # doctest: +SKIP
        """

        self._trading.close_all_positions(cancel_orders=True)

    # Release the connection
    def close(self):
        """
        Nothing to release: Alpaca is stateless REST.

        Parameters
        ----------
        None

        Returns
        -------
        None

        Examples
        --------
        >>> broker = AlpacaBroker("STRATEGY_EXAMPLE")  # doctest: +SKIP
        >>> broker.close()  # doctest: +SKIP
        """
