'''
order_limits.py - risk_orders: planned orders within config.yaml paper.limits
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
