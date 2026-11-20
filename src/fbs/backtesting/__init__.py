'''
fbs.backtesting - Backtest of a strategy's target weights. Used by the live
runner's dry-run report and performance report. Pure functions, no I/O.

Files:
    backtest_engine.py      backtest        daily returns of the held weights, t+2 timing
    performance_metrics.py  metrics         annual return / vol / Sharpe / max drawdown
    sample_split.py         split_segments  IS / Embargo / OOS labels
'''

from fbs.backtesting.backtest_engine import backtest
from fbs.backtesting.performance_metrics import BARS_PER_YEAR, metrics
from fbs.backtesting.sample_split import split_segments

__all__ = ["backtest", "metrics", "split_segments", "BARS_PER_YEAR"]
