"""Turn target weights into whole-share order intents. Pure functions, no I/O."""

from __future__ import annotations

from datetime import date

import pandas as pd

from fbs.live.broker import AssetInfo, OrderIntent

DUST_WEIGHT = 1e-6


def rebalance_sessions(sessions: list[date], rule: str) -> set[date]:
    """Signal sessions on which the strategy rebalances.

    D: every session. W: last session of each week. M: last session of each month.
    A session is the last of its period when the next session falls in a new period.
    """
    if rule == "D":
        return set(sessions)
    out = set()
    for today, nxt in zip(sessions, sessions[1:]):
        if rule == "W" and today.isocalendar()[:2] != nxt.isocalendar()[:2]:
            out.add(today)
        if rule == "M" and (today.year, today.month) != (nxt.year, nxt.month):
            out.add(today)
    return out


def clean_targets(weights: pd.Series, assets: dict[str, AssetInfo], allow_shorts: bool
                  ) -> tuple[dict[str, float], list[str]]:
    """Drop NaN, dust, untradable names and disallowed shorts. Returns targets and notes."""
    targets, notes = {}, []
    for symbol, w in weights.dropna().items():
        w = float(w)
        if abs(w) < DUST_WEIGHT:
            continue
        info = assets.get(symbol)
        if info is None or not info.tradable:
            notes.append(f"{symbol}: not tradable on Alpaca, target set to 0")
            continue
        if w < 0 and not (allow_shorts and info.shortable and info.easy_to_borrow):
            notes.append(f"{symbol}: short not allowed or not borrowable, target set to 0")
            continue
        targets[symbol] = w
    return targets, notes


def plan_orders(targets: dict[str, float], positions: dict[str, int], prices: dict[str, float],
                capital: float, buying_power: float, min_order_notional: float,
                strategy: str, exec_session: date) -> tuple[list[OrderIntent], list[str]]:
    """Whole-share orders that move `positions` to `targets` (fractions of `capital`).

    Sells and reductions come first, then buys. A trade that flips the sign of a position is
    split into a closing leg and an opening leg. Buys are scaled down if buying power is short.
    The client_order_id is deterministic, so a re-run for the same session never duplicates.
    """
    notes: list[str] = []
    target_qty: dict[str, int] = {}
    for symbol in sorted(set(targets) | set(positions)):
        w = targets.get(symbol, 0.0)
        if w == 0.0:
            target_qty[symbol] = 0
            continue
        price = prices.get(symbol)
        if not price or price <= 0:
            notes.append(f"{symbol}: no price, position left unchanged")
            target_qty[symbol] = positions.get(symbol, 0)
            continue
        target_qty[symbol] = int(round(w * capital / price))

    sells: list[OrderIntent] = []
    buys: list[OrderIntent] = []
    for symbol, tgt in target_qty.items():
        cur = positions.get(symbol, 0)
        if tgt == cur:
            continue
        price = prices.get(symbol, 0.0)
        if cur != 0 and tgt != 0 and (cur > 0) != (tgt > 0):      # sign flip: close, then open
            legs = [(-cur, "close"), (tgt, "open")]
        else:
            legs = [(tgt - cur, "close" if tgt == 0 else "adjust")]
        for delta, leg in legs:
            if price and abs(delta) * price < min_order_notional and tgt != 0:
                notes.append(f"{symbol}: trade of {delta} shares below min notional, skipped")
                continue
            side = "buy" if delta > 0 else "sell"
            intent = OrderIntent(
                symbol=symbol, side=side, qty=abs(delta),
                client_order_id=f"{strategy}-{exec_session.isoformat()}-{symbol}-{leg}",
                target_weight=targets.get(symbol, 0.0), reason=leg,
            )
            (buys if side == "buy" else sells).append(intent)

    sell_proceeds = sum(o.qty * prices.get(o.symbol, 0.0) for o in sells)
    buy_cost = sum(o.qty * prices.get(o.symbol, 0.0) for o in buys)
    available = buying_power + sell_proceeds
    if buy_cost > available > 0:
        scale = available / buy_cost
        notes.append(f"buys scaled by {scale:.3f}: cost {buy_cost:,.0f} > available {available:,.0f}")
        buys = [OrderIntent(o.symbol, o.side, int(o.qty * scale), o.client_order_id, o.target_weight, o.reason)
                for o in buys]
        buys = [o for o in buys if o.qty > 0]
    return sells + buys, notes


def turnover(orders: list[OrderIntent], prices: dict[str, float], capital: float) -> float:
    """One-way turnover: half the traded value, as a fraction of capital."""
    traded = sum(o.qty * prices.get(o.symbol, 0.0) for o in orders)
    return traded / capital / 2 if capital else 0.0
