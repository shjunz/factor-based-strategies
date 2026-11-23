'''
order_submit.py - Send the planned orders to the broker as market-on-close.

execution_submit_gate  reasons orders cannot be sent now (disabled, closed, too late)
execution_submit       send each order once; skip any already sent for the session

The only file in fbs.execution that talks to the broker; it gets the broker
passed in, so it works with any adapter in fbs.live.brokers.
'''

# %%
# Submit

# May orders be sent now?
def execution_submit_gate(paper, clock):
    """
    Reasons orders cannot be sent now: strategy disabled, market closed, or too
    close to the market-on-close cut-off.

    Parameters
    ----------
    paper : dict
        config.yaml paper: enabled, moc_cutoff_minutes.
    clock : MarketClock
        Market clock.

    Returns
    -------
    gate : list of str
        Empty if orders may be sent.

    Examples
    --------
    >>> from datetime import datetime
    >>> from types import SimpleNamespace as Clock
    >>> from zoneinfo import ZoneInfo
    >>> NY = ZoneInfo("America/New_York")
    >>> open_clock = Clock(timestamp=datetime(2024, 12, 31, 10, 0, tzinfo=NY), is_open=True,
    ...                    next_close=datetime(2024, 12, 31, 16, 0, tzinfo=NY))
    >>> execution_submit_gate({"enabled": True}, open_clock)
    []
    >>> late = Clock(timestamp=datetime(2024, 12, 31, 15, 50, tzinfo=NY), is_open=True,
    ...              next_close=datetime(2024, 12, 31, 16, 0, tzinfo=NY))
    >>> execution_submit_gate({"enabled": False, "moc_cutoff_minutes": 15}, late)
    ['config.yaml paper.enabled is false', 'only 10 min to the close; MOC cut-off buffer is 15 min']
    """

    gate = []
    if not paper["enabled"]:
        gate.append("config.yaml paper.enabled is false")
    if not clock.is_open:
        gate.append("market is closed")
    minutes_left = (clock.next_close - clock.timestamp).total_seconds() / 60
    cutoff = float(paper.get("moc_cutoff_minutes", 15))
    if clock.is_open and minutes_left < cutoff:
        gate.append(f"only {minutes_left:.0f} min to the close; MOC cut-off buffer is {cutoff:.0f} min")

    return gate

# Send orders
def execution_submit(broker, orders, prefix, since):
    """
    Send the orders as market-on-close, skipping any already sent.

    Parameters
    ----------
    broker : Broker
        The strategy's broker.
    orders : list of OrderIntent
        Orders to send.
    prefix : str
        client_order_id prefix of this strategy and session.
    since : datetime
        Look for already-sent orders after this time.

    Returns
    -------
    submitted : list of dict
        client_order_id and status of each order.

    Examples
    --------
    >>> from datetime import datetime
    >>> from types import SimpleNamespace as Broker
    >>> from fbs.live.brokers import OrderIntent
    >>> broker = Broker(
    ...     orders_with_prefix=lambda prefix, since: [
    ...         Broker(client_order_id="demo-2024-12-31-SPY-adjust")],
    ...     submit_moc=lambda order: "accepted")
    >>> orders = [OrderIntent("SPY", "buy", 10, "demo-2024-12-31-SPY-adjust", 0.5, "adjust"),
    ...           OrderIntent("QQQ", "buy", 125, "demo-2024-12-31-QQQ-adjust", 0.5, "adjust")]
    >>> execution_submit(broker, orders, "demo-2024-12-31-", datetime(2024, 12, 28))
      demo-2024-12-31-QQQ-adjust: accepted
    [{'client_order_id': 'demo-2024-12-31-SPY-adjust', 'status': 'already_present'}, {'client_order_id': 'demo-2024-12-31-QQQ-adjust', 'status': 'accepted'}]
    """

    # Orders already sent for this session, e.g. by an earlier run
    existing = {o.client_order_id for o in broker.orders_with_prefix(prefix, since)}

    submitted = []
    for o in orders:
        if o.client_order_id in existing:
            submitted.append({"client_order_id": o.client_order_id, "status": "already_present"})
            continue
        try:
            status = broker.submit_moc(o)
        except Exception as exc:   # one rejected order must not stop the others
            status = f"rejected: {exc}"
        submitted.append({"client_order_id": o.client_order_id, "status": status})
        print(f"  {o.client_order_id}: {status}")

    return submitted
