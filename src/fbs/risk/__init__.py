'''
fbs.risk - Risk gates: decide whether a rebalance may trade at all.
Each function returns a list of failures; any failure blocks the run and no
orders are sent. Pure functions, no I/O.

Two parts, split by whether the orders exist yet:
    pre_trade/   before fbs.execution: data, target weights, account
    post_trade/  after fbs.execution: the whole-share orders

Order runner.py calls them in:
    pre_trade/data_freshness.py  risk_input_data
    pre_trade/weight_limits.py   risk_weights
    pre_trade/account_status.py  risk_account
    post_trade/order_limits.py   risk_orders
'''

from fbs.risk.post_trade import risk_orders
from fbs.risk.pre_trade import risk_account, risk_input_data, risk_weights

__all__ = ["risk_input_data", "risk_weights", "risk_account", "risk_orders"]
