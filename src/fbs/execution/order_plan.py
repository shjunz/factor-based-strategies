'''
order_plan.py - execution_plan_orders: target weights -> whole-share orders;
execution_turnover: one-way turnover of those orders.
'''

# %%
# Imports

from dataclasses import replace

from fbs.live.brokers import OrderIntent

# %%
# Orders

# Whole-share orders from targets
def execution_plan_orders(targets, positions, prices, capital, buying_power, min_order_notional,
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

    Examples
    --------
    >>> from datetime import date
    >>> prices = {"SPY": 500.0, "QQQ": 400.0, "IWM": 200.0}
    >>> orders, notes = execution_plan_orders(
    ...     {"SPY": 0.5, "QQQ": 0.5}, {"SPY": 100, "IWM": 10}, prices,
    ...     capital=100_000, buying_power=100_000, min_order_notional=100,
    ...     strategy="demo", exec_session=date(2024, 1, 3))
    >>> [(o.side, o.symbol, o.qty, o.client_order_id) for o in orders]
    [('sell', 'IWM', 10, 'demo-2024-01-03-IWM-close'), ('buy', 'QQQ', 125, 'demo-2024-01-03-QQQ-adjust')]

    Buys are scaled down when buying power is short:

    >>> orders, notes = execution_plan_orders(
    ...     {"SPY": 1.0}, {}, prices, capital=100_000, buying_power=50_000,
    ...     min_order_notional=100, strategy="demo", exec_session=date(2024, 1, 3))
    >>> [(o.side, o.symbol, o.qty) for o in orders], notes
    ([('buy', 'SPY', 100)], ['buys scaled by 0.500: cost 100,000 > available 50,000'])
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
def execution_turnover(orders, prices, capital):
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

    Examples
    --------
    >>> orders = [OrderIntent("IWM", "sell", 10, "demo-2024-01-03-IWM-close", 0.0, "close"),
    ...           OrderIntent("QQQ", "buy", 125, "demo-2024-01-03-QQQ-adjust", 0.5, "adjust")]
    >>> execution_turnover(orders, {"IWM": 200.0, "QQQ": 400.0}, 100_000)
    0.26
    >>> execution_turnover(orders, {"IWM": 200.0, "QQQ": 400.0}, 0)
    0.0
    """

    traded = sum(o.qty * prices.get(o.symbol, 0.0) for o in orders)
    to = traded / capital / 2 if capital else 0.0

    return to
