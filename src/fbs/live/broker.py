"""Broker adapter. AlpacaBroker is the only code in the repo that talks to the Alpaca trading API."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, datetime

from dotenv import load_dotenv

PAPER_URL_FRAGMENT = "paper-api.alpaca.markets"


@dataclass(frozen=True)
class OrderIntent:
    symbol: str
    side: str            # "buy" or "sell"
    qty: int             # whole shares, > 0
    client_order_id: str
    target_weight: float
    reason: str


@dataclass(frozen=True)
class AccountState:
    equity: float
    buying_power: float
    status: str
    trading_blocked: bool
    account_blocked: bool


@dataclass(frozen=True)
class AssetInfo:
    tradable: bool
    shortable: bool
    easy_to_borrow: bool


def credentials(account: str) -> tuple[str, str]:
    """Keys come from ALPACA_{ACCOUNT}_KEY / ALPACA_{ACCOUNT}_SECRET (environment or .env)."""
    load_dotenv()
    prefix = f"ALPACA_{account.upper()}"
    key, secret = os.getenv(f"{prefix}_KEY"), os.getenv(f"{prefix}_SECRET")
    if not key or not secret:
        raise RuntimeError(f"set {prefix}_KEY and {prefix}_SECRET in the environment or .env")
    return key, secret


class AlpacaBroker:
    """Alpaca paper trading only. Construction fails for anything that is not a paper account."""

    def __init__(self, account: str, mode: str = "paper"):
        if mode != "paper":
            raise ValueError("AlpacaBroker only supports mode='paper'")
        from alpaca.data.historical import StockHistoricalDataClient
        from alpaca.trading.client import TradingClient

        key, secret = credentials(account)
        self._trading = TradingClient(key, secret, paper=True)
        base_url = getattr(self._trading._base_url, "value", self._trading._base_url)  # alpaca-py stores an enum
        if PAPER_URL_FRAGMENT not in str(base_url):
            raise RuntimeError("refusing to trade: client is not pointed at the Alpaca paper endpoint")
        self._data = StockHistoricalDataClient(key, secret)

    # --- market calendar ---------------------------------------------------------------
    def clock(self):
        """Alpaca clock: .timestamp, .is_open, .next_open, .next_close."""
        return self._trading.get_clock()

    def sessions(self, start: date, end: date) -> list[date]:
        from alpaca.trading.requests import GetCalendarRequest
        return [c.date for c in self._trading.get_calendar(GetCalendarRequest(start=start, end=end))]

    # --- account state -----------------------------------------------------------------
    def account(self) -> AccountState:
        a = self._trading.get_account()
        return AccountState(float(a.equity), float(a.buying_power), str(a.status),
                            bool(a.trading_blocked), bool(a.account_blocked))

    def positions(self) -> dict[str, int]:
        return {p.symbol: int(float(p.qty)) for p in self._trading.get_all_positions()}

    def asset(self, symbol: str) -> AssetInfo:
        try:
            a = self._trading.get_asset(symbol)
        except Exception:
            return AssetInfo(False, False, False)
        active = str(a.status).lower().endswith("active")
        return AssetInfo(bool(a.tradable) and active, bool(a.shortable), bool(a.easy_to_borrow))

    def latest_prices(self, symbols: list[str]) -> dict[str, float]:
        from alpaca.data.requests import StockLatestTradeRequest
        if not symbols:
            return {}
        trades = self._data.get_stock_latest_trade(StockLatestTradeRequest(symbol_or_symbols=symbols))
        return {s: float(t.price) for s, t in trades.items()}

    # --- orders ------------------------------------------------------------------------
    def orders_with_prefix(self, prefix: str, since: datetime) -> list:
        from alpaca.trading.enums import QueryOrderStatus
        from alpaca.trading.requests import GetOrdersRequest
        orders = self._trading.get_orders(
            GetOrdersRequest(status=QueryOrderStatus.ALL, after=since, limit=500))
        return [o for o in orders if (o.client_order_id or "").startswith(prefix)]

    def submit_moc(self, intent: OrderIntent) -> str:
        from alpaca.trading.enums import OrderSide, TimeInForce
        from alpaca.trading.requests import MarketOrderRequest
        order = self._trading.submit_order(MarketOrderRequest(
            symbol=intent.symbol,
            qty=intent.qty,
            side=OrderSide.BUY if intent.side == "buy" else OrderSide.SELL,
            time_in_force=TimeInForce.CLS,
            client_order_id=intent.client_order_id,
        ))
        return str(order.status)

    def cancel_all(self) -> None:
        self._trading.cancel_orders()

    def close_all_positions(self) -> None:
        self._trading.close_all_positions(cancel_orders=True)
