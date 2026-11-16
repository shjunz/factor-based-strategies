"""Pre-trade checks. Any failure blocks the run: no orders are sent."""

from __future__ import annotations

import math
from datetime import date

import pandas as pd

from fbs.live.broker import AccountState, OrderIntent


def check_weights(weights: pd.Series, limits: dict) -> list[str]:
    w = weights.dropna().astype(float)
    failures = []
    if not all(math.isfinite(x) for x in w):
        failures.append("weights contain inf")
        return failures
    if w.abs().sum() > limits["max_gross"] + 1e-9:
        failures.append(f"gross {w.abs().sum():.3f} > max_gross {limits['max_gross']}")
    if abs(w.sum()) > limits["max_net"] + 1e-9:
        failures.append(f"net {w.sum():.3f} > max_net {limits['max_net']}")
    if len(w) and w.abs().max() > limits["max_weight"] + 1e-9:
        failures.append(f"max weight {w.abs().max():.3f} > max_weight {limits['max_weight']}")
    if not limits["allow_shorts"] and (w < 0).any():
        failures.append("negative weights but allow_shorts is false")
    return failures


def check_data(data: pd.DataFrame, signal_session: date) -> list[str]:
    if data.empty:
        return ["data is empty"]
    last = pd.Timestamp(data.index.max()).date()
    if last != signal_session:
        return [f"stale data: last session {last}, expected {signal_session}"]
    return []


def check_account(account: AccountState, capital: float) -> list[str]:
    failures = []
    if not account.status.upper().endswith("ACTIVE"):
        failures.append(f"account status {account.status}")
    if account.trading_blocked or account.account_blocked:
        failures.append("account is blocked")
    if capital > account.equity:
        failures.append(f"capital {capital:,.0f} > account equity {account.equity:,.0f}")
    return failures


def check_orders(orders: list[OrderIntent], prices: dict[str, float], turnover: float, limits: dict) -> list[str]:
    failures = []
    if len(orders) > limits["max_orders"]:
        failures.append(f"{len(orders)} orders > max_orders {limits['max_orders']}")
    for o in orders:
        notional = o.qty * prices.get(o.symbol, 0.0)
        if notional > limits["max_order_notional"]:
            failures.append(f"{o.symbol} order {notional:,.0f} > max_order_notional {limits['max_order_notional']}")
    if turnover > limits["max_turnover"]:
        failures.append(f"turnover {turnover:.2f} > max_turnover {limits['max_turnover']}")
    return failures
