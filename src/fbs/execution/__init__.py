'''
fbs.execution - How approved target weights become orders, and how the orders
are sent. Pure functions except order_submit.py, which is given the broker.

Files (in the order runner.py calls them):
    rebalance_sessions.py  execution_rebalance_sessions    which signal sessions rebalance
    tradable_assets.py     execution_remove_invalid_assets drop untradable / unshortable names
    order_plan.py          execution_plan_orders           target weights -> whole-share orders
                           execution_turnover              one-way turnover of the orders
    order_submit.py        execution_submit_gate           enabled, market open, before the MOC cut-off
                           execution_submit                send market-on-close orders, never twice
'''

from fbs.execution.order_plan import execution_plan_orders, execution_turnover
from fbs.execution.order_submit import execution_submit, execution_submit_gate
from fbs.execution.rebalance_sessions import execution_rebalance_sessions
from fbs.execution.tradable_assets import execution_remove_invalid_assets

__all__ = ["execution_rebalance_sessions", "execution_remove_invalid_assets",
           "execution_plan_orders", "execution_turnover",
           "execution_submit_gate", "execution_submit"]
