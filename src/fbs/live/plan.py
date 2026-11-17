'''
plan.py - Rebalance sessions and target weights -> whole-share orders. Pure
functions, no I/O.
'''

# %%
# Imports

from dataclasses import replace

from fbs.live.broker import OrderIntent

# %%
# Constants

# Weights smaller than this are treated as 0
DUST_WEIGHT = 1e-6

# %%
# Rebalance Sessions

# Rebalance sessions of a rule
def rebalance_sessions(sessions, rule):
    """
    Signal sessions on which the strategy rebalances. A session is the last of
    its week or month when the next session falls in a new one.

    Parameters
    ----------
    sessions : list of date
        Trading sessions, ascending.
    rule : {"D", "W", "M"}
        D: every session. W: last session of each week. M: last session of
        each month.

    Returns
    -------
    rebalance : set of date
        Rebalance sessions. The last session of `sessions` is never one for W
        or M, since its next session is unknown.
    """

    # Every session
    if rule == "D":
        return set(sessions)

    # Sessions whose next session starts a new week or month
    rebalance = set()
    for today, nxt in zip(sessions, sessions[1:]):
        if rule == "W" and today.isocalendar()[:2] != nxt.isocalendar()[:2]:
            rebalance.add(today)
        if rule == "M" and (today.year, today.month) != (nxt.year, nxt.month):
            rebalance.add(today)

    return rebalance

# %%
# Targets

# Tradable target weights
def clean_targets(weights, assets, allow_shorts):
    """
    Drop NaN, dust, untradable symbols and disallowed shorts from the target
    weights.

    Parameters
    ----------
    weights : pd.Series
        Target weight per symbol.
    assets : dict of str to AssetInfo
        Alpaca permissions per symbol.
    allow_shorts : bool
        config.yaml paper.limits allow_shorts.

    Returns
    -------
    targets : dict of str to float
        Weights that can be traded.
    notes : list of str
        One line per dropped symbol.
    """

    targets, notes = {}, []
    for symbol, w in weights.dropna().items():
        w = float(w)

        # Dust
        if abs(w) < DUST_WEIGHT:
            continue

        # Not tradable on Alpaca
        info = assets.get(symbol)
        if info is None or not info.tradable:
            notes.append(f"{symbol}: not tradable on Alpaca, target set to 0")
            continue

        # Short not allowed or not borrowable
        if w < 0 and not (allow_shorts and info.shortable and info.easy_to_borrow):
            notes.append(f"{symbol}: short not allowed or not borrowable, target set to 0")
            continue

        targets[symbol] = w

    return targets, notes

# %%
# Orders

# Whole-share orders from targets
def plan_orders(targets, positions, prices, capital, buying_power, min_order_notional,
                strategy, exec_session):
    """
    Whole-share orders that move the positions to the target weights.

    Sells come first, then buys. A trade that flips the sign of a position is
    split into a closing leg and an opening leg. Buys are scaled down if
    buying power is short.

    Parameters
    ----------
    targets : dict of str to float
        Target weight per symbol, as a fraction of `capital`.
    positions : dict of str to int
        Current shares per symbol.
    prices : dict of str to float
        Latest price per symbol.
    capital : float
        config.yaml paper.capital in USD.
    buying_power : float
        Account buying power in USD.
    min_order_notional : float
        Smaller trades are skipped, except closing a position.
    strategy : str
        Strategy name, first part of client_order_id.
    exec_session : date
        Execution session, second part of client_order_id.

    Returns
    -------
    orders : list of OrderIntent
        Sells, then buys.
    notes : list of str
        Skipped trades and scaling.
    """

    notes = []

    # Target shares: weight * capital / price, rounded; positions without a price stay as they are
    target_qty = {}
    for symbol in sorted(set(targets) | set(positions)):
        w = targets.get(symbol, 0.0)
        price = prices.get(symbol)
        if w == 0.0:
            target_qty[symbol] = 0
        elif not price or price <= 0:
            notes.append(f"{symbol}: no price, position left unchanged")
            target_qty[symbol] = positions.get(symbol, 0)
        else:
            target_qty[symbol] = int(round(w * capital / price))

    # One order per leg from current to target shares
    sells, buys = [], []
    for symbol, tgt in target_qty.items():
        cur = positions.get(symbol, 0)
        if tgt == cur:
            continue

        # A sign flip is two legs: close the old position, then open the new one
        if cur != 0 and tgt != 0 and (cur > 0) != (tgt > 0):
            legs = [(-cur, "close"), (tgt, "open")]
        else:
            legs = [(tgt - cur, "close" if tgt == 0 else "adjust")]

        price = prices.get(symbol, 0.0)
        for delta, reason in legs:
            # Skip small trades, but always close a position fully
            if price and abs(delta) * price < min_order_notional and tgt != 0:
                notes.append(f"{symbol}: trade of {delta} shares below min notional, skipped")
                continue
            side = "buy" if delta > 0 else "sell"
            intent = OrderIntent(
                symbol=symbol, side=side, qty=abs(delta),
                client_order_id=f"{strategy}-{exec_session.isoformat()}-{symbol}-{reason}",
                target_weight=targets.get(symbol, 0.0), reason=reason,
            )
            (buys if side == "buy" else sells).append(intent)

    # Scale buys down to buying power plus sell proceeds
    sell_proceeds = sum(o.qty * prices.get(o.symbol, 0.0) for o in sells)
    buy_cost = sum(o.qty * prices.get(o.symbol, 0.0) for o in buys)
    available = buying_power + sell_proceeds
    if buy_cost > available > 0:
        scale = available / buy_cost
        notes.append(f"buys scaled by {scale:.3f}: cost {buy_cost:,.0f} > available {available:,.0f}")
        buys = [replace(o, qty=int(o.qty * scale)) for o in buys]
        buys = [o for o in buys if o.qty > 0]

    orders = sells + buys

    return orders, notes

# One-way turnover
def turnover(orders, prices, capital):
    """
    One-way turnover: half the traded value, as a fraction of capital.

    Parameters
    ----------
    orders : list of OrderIntent
        Planned orders.
    prices : dict of str to float
        Latest price per symbol.
    capital : float
        config.yaml paper.capital in USD.

    Returns
    -------
    to : float
        Turnover, 0 if capital is 0.
    """

    traded = sum(o.qty * prices.get(o.symbol, 0.0) for o in orders)
    to = traded / capital / 2 if capital else 0.0

    return to
