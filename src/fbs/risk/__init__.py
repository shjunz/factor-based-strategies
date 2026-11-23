'''
fbs.risk - Risk checks before the orders are sent, and fill reconciliation
after they are filled.

Two parts, split by whether the orders have been sent:
    pre_trade/   before submitting: data, target weights, account, then the
                 whole-share orders. Each returns a list of failures; any
                 failure blocks the run and no orders are sent.
    post_trade/  after the close (the `performance` command): fills against
                 the close, and the live report PDF. Planned: drawdown.py.

Order runner.py calls them in:
    pre_trade/data_freshness.py  risk_input_data
    pre_trade/weight_limits.py   risk_weights
    pre_trade/account_status.py  risk_account
    pre_trade/order_limits.py    risk_orders      (after fbs.execution plans the orders)
    post_trade/fills.py          risk_fills, risk_fill_summary
    post_trade/live_report.py    write_live_report
'''

from fbs.risk.post_trade import risk_fill_summary, risk_fills
from fbs.risk.pre_trade import risk_account, risk_input_data, risk_orders, risk_weights

__all__ = ["risk_input_data", "risk_weights", "risk_account", "risk_orders",
           "risk_fills", "risk_fill_summary"]
