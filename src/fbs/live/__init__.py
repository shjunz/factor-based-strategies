"""Paper trading runner: takes a strategy folder under strategy/ and trades it on Alpaca paper.

Usage (from the repo root):
    python -m fbs.live rebalance strategy_example            # dry run: print planned orders
    python -m fbs.live rebalance strategy_example --submit   # send market-on-close orders
    python -m fbs.live status strategy_example
    python -m fbs.live halt strategy_example                 # cancel open orders
    python -m fbs.live flatten strategy_example --yes        # cancel orders + close all positions
"""
