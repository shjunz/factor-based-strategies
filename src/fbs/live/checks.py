'''
checks.py - Pre-trade checks. Each returns a list of failures; any failure
blocks the run and no orders are sent.
'''

# %%
# Imports

import numpy as np
import pandas as pd

# %%
# Constants

# Tolerance for float sums compared with config.yaml paper.limits
TOL = 1e-9

# %%
# Checks

# Data check
def check_data(data, signal_session):
    """
    Check the data is not empty and includes the signal session.

    Parameters
    ----------
    data : pd.DataFrame
        Output of the strategy's data.fetch. Index = session dates.
    signal_session : date
        Session the weights are computed for.

    Returns
    -------
    failures : list of str
        Empty if the data is usable.
    """

    # No rows at all
    if data.empty:
        return ["data is empty"]

    # Last row must be the signal session, else the source has not published it yet
    last = pd.Timestamp(data.index.max()).date()
    if last != signal_session:
        return [f"stale data: last session {last}, expected {signal_session}"]

    return []

# Weights check
def check_weights(weights, limits):
    """
    Check the signal session's target weights against the config.yaml paper.limits.

    Parameters
    ----------
    weights : pd.Series
        Target weight per symbol.
    limits : dict
        config.yaml paper.limits: max_gross, max_net, max_weight, allow_shorts.

    Returns
    -------
    failures : list of str
        Empty if all limits hold.
    """

    w = weights.dropna().astype(float)

    # Infinite weights make every other check meaningless
    if not np.isfinite(w).all():
        return ["weights contain inf"]

    # Gross, net and single-name exposure
    failures = []
    if w.abs().sum() > limits["max_gross"] + TOL:
        failures.append(f"gross {w.abs().sum():.3f} > max_gross {limits['max_gross']}")
    if abs(w.sum()) > limits["max_net"] + TOL:
        failures.append(f"net {w.sum():.3f} > max_net {limits['max_net']}")
    if len(w) and w.abs().max() > limits["max_weight"] + TOL:
        failures.append(f"max weight {w.abs().max():.3f} > max_weight {limits['max_weight']}")

    # Shorts only when allowed
    if not limits["allow_shorts"] and (w < 0).any():
        failures.append("negative weights but allow_shorts is false")

    return failures

# Account check
def check_account(account, capital):
    """
    Check the account is active, not blocked, and holds the strategy's capital.

    Parameters
    ----------
    account : AccountState
        Current account summary.
    capital : float
        config.yaml paper.capital in USD.

    Returns
    -------
    failures : list of str
        Empty if the account can trade.
    """

    failures = []
    if not account.status.upper().endswith("ACTIVE"):
        failures.append(f"account status {account.status}")
    if account.trading_blocked or account.account_blocked:
        failures.append("account is blocked")
    if capital > account.equity:
        failures.append(f"capital {capital:,.0f} > account equity {account.equity:,.0f}")

    return failures

# Orders check
def check_orders(orders, prices, turnover, limits):
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
