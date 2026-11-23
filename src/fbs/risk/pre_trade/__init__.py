'''
fbs.risk.pre_trade - Checks before any order is sent: is the data fresh, are
the target weights inside the limits, is the account usable, are the planned
whole-share orders inside the limits. Any failure blocks the whole rebalance.

Files (in the order runner.py calls them):
    data_freshness.py  risk_input_data  data not empty, reaches the signal session
    weight_limits.py   risk_weights     gross / net / single-name / shorts
    account_status.py  risk_account     account active, not blocked, capital <= equity
    order_limits.py    risk_orders      order count / order size / turnover (after fbs.execution plans them)
'''

from fbs.risk.pre_trade.account_status import risk_account
from fbs.risk.pre_trade.data_freshness import risk_input_data
from fbs.risk.pre_trade.order_limits import risk_orders
from fbs.risk.pre_trade.weight_limits import risk_weights

__all__ = ["risk_input_data", "risk_weights", "risk_account", "risk_orders"]
