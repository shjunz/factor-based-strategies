'''
fbs.live - Paper trading runner: trades a strategy folder under strategy/ on
Alpaca paper.

Usage (from the repo root):
    python -m fbs.live rebalance strategy_example            # dry run: record + dry-run PDF in records/
    python -m fbs.live rebalance strategy_example --submit   # send market-on-close orders
    python -m fbs.live status strategy_example
    python -m fbs.live performance strategy_example          # live report: live vs backtest PDF in records/
    python -m fbs.live halt strategy_example                 # cancel open orders
    python -m fbs.live flatten strategy_example --yes        # cancel orders + close all positions

Reading order:
    __main__.py  command line
    runner.py    one run, step by step: rebalance, status, performance, halt
    loader.py    read and check the strategy folder
    broker.py    the only file that talks to Alpaca
    report.py    PDF reports: dry-run report (before going live) and live report (after)

Shared with other packages:
    fbs.risk       risk gates: pre_trade (data, weights, account), post_trade (orders)
    fbs.execution  rebalance sessions, target weights -> whole-share orders
'''
