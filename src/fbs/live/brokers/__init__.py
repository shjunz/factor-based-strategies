'''
fbs.live.brokers - Broker adapters. config.yaml paper.broker picks one;
everything else in the repo only sees the records and methods in base.py.

Files:
    base.py    records (OrderIntent, AccountState, AssetInfo, MarketClock,
               OrderRecord) and the Broker interface
    alpaca.py  AlpacaBroker: Alpaca paper, REST via alpaca-py
    ibkr.py    IBKRBroker: Interactive Brokers paper, via TWS / IB Gateway and ib_async
'''

from fbs.live.brokers.base import (AccountState, AssetInfo, Broker, MarketClock, OrderIntent,
                                   OrderRecord)

# config.yaml paper.broker values
BROKERS = ("alpaca", "ibkr")

# Broker of one strategy
def make_broker(strategy):
    """
    Connect the broker named by config.yaml paper.broker (default "alpaca").

    Parameters
    ----------
    strategy : Strategy
        The loaded strategy.

    Returns
    -------
    broker : Broker
        AlpacaBroker or IBKRBroker.

    Raises
    ------
    ValueError
        If paper.broker is not one of BROKERS.

    Examples
    --------
    >>> from types import SimpleNamespace as Strategy
    >>> make_broker(Strategy(paper={"broker": "schwab", "account": "X"}))
    Traceback (most recent call last):
    ...
    ValueError: config.yaml paper.broker must be one of ('alpaca', 'ibkr'), got 'schwab'
    """

    paper = strategy.paper
    name = paper.get("broker", "alpaca")
    mode = paper.get("mode", "paper")

    if name == "alpaca":
        from fbs.live.brokers.alpaca import AlpacaBroker
        return AlpacaBroker(paper["account"], mode)
    if name == "ibkr":
        from fbs.live.brokers.ibkr import IBKRBroker
        return IBKRBroker(paper["account"], mode, state_dir=strategy.folder / "records")
    raise ValueError(f"config.yaml paper.broker must be one of {BROKERS}, got {name!r}")


__all__ = ["BROKERS", "make_broker", "Broker", "OrderIntent", "AccountState", "AssetInfo",
           "MarketClock", "OrderRecord"]
