'''
fbs.risk.post_trade - Checks after fbs.execution has turned the approved
weights into whole-share orders: are the orders themselves inside the limits.
Any failure blocks the whole rebalance. Planned: drawdown.py (scale exposure
after a drawdown, from realised equity).

Files:
    order_limits.py    risk_orders      order count / order size / turnover
'''

from fbs.risk.post_trade.order_limits import risk_orders

__all__ = ["risk_orders"]
