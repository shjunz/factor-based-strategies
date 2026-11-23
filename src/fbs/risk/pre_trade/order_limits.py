'''
order_limits.py - risk_orders (pre-trade, after fbs.execution plans the orders): planned orders within config.yaml paper.limits
(number of orders, size of each order, one-way turnover).
'''

# %%
# Checks

# Orders check
def risk_orders(orders, prices, turnover, limits):
    """
    Check the planned orders against the config.yaml paper.limits.

    Parameters
    ----------
    orders : list of OrderIntent
        Planned orders.
    prices : dict of str to float
        Latest price per symbol.
    turnover : float
        One-way turnover of the orders, as a fraction of capital.
    limits : dict
        config.yaml paper.limits: max_orders, max_order_notional, max_turnover.

    Returns
    -------
    failures : list of str
        Empty if all limits hold.

    Examples
    --------
    >>> from fbs.live.brokers import OrderIntent
    >>> orders = [OrderIntent("IWM", "sell", 10, "demo-2024-01-03-IWM-close", 0.0, "close"),
    ...           OrderIntent("QQQ", "buy", 125, "demo-2024-01-03-QQQ-adjust", 0.5, "adjust")]
    >>> prices = {"IWM": 200.0, "QQQ": 400.0}
    >>> limits = {"max_orders": 1, "max_order_notional": 20_000, "max_turnover": 0.5}
    >>> risk_orders(orders, prices, turnover=0.26, limits=limits)
    ['2 orders > max_orders 1', 'QQQ order 50,000 > max_order_notional 20000']
    >>> risk_orders(orders[:1], prices, turnover=0.01, limits=limits)
    []
    """

    failures = []

    # Number of orders
    if len(orders) > limits["max_orders"]:
        failures.append(f"{len(orders)} orders > max_orders {limits['max_orders']}")

    # Size of each order
    for o in orders:
        notional = o.qty * prices.get(o.symbol, 0.0)
        if notional > limits["max_order_notional"]:
            failures.append(f"{o.symbol} order {notional:,.0f} > max_order_notional {limits['max_order_notional']}")

    # Total traded value
    if turnover > limits["max_turnover"]:
        failures.append(f"turnover {turnover:.2f} > max_turnover {limits['max_turnover']}")

    return failures
