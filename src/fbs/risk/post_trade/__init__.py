'''
fbs.risk.post_trade - After the orders are sent and filled: record how each
whole-share order filled against the close, and write the live report PDF.
Runs after the close (the `performance` command), since market-on-close
orders fill at the close. Planned: drawdown.py (scale exposure after a
drawdown, from realised equity).

Files:
    fills.py        risk_fills, risk_fill_summary  fill, close and slippage per order
    live_report.py  write_live_report              live vs backtest, fills (needs matplotlib)
'''

from fbs.risk.post_trade.fills import risk_fill_summary, risk_fills

__all__ = ["risk_fills", "risk_fill_summary"]
