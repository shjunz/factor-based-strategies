'''
rebalance_sessions.py - execution_rebalance_sessions: signal sessions on which
a D / W / M rule rebalances.
'''

# %%
# Rebalance Sessions

# Rebalance sessions of a rule
def execution_rebalance_sessions(sessions, rule):
    """
    Signal sessions on which the strategy rebalances. A session is the last of
    its week or month when the next session falls in a new one.

    Parameters
    ----------
    sessions : list of date
        Trading sessions, ascending.
    rule : {"D", "W", "M"}
        D: every session. W: last session of each week. M: last session of
        each month.

    Returns
    -------
    rebalance : set of date
        Rebalance sessions. The last session of `sessions` is never one for W
        or M, since its next session is unknown.

    Examples
    --------
    >>> from datetime import date
    >>> sessions = [date(2024, 1, 29), date(2024, 1, 30), date(2024, 1, 31),
    ...             date(2024, 2, 1), date(2024, 2, 2), date(2024, 2, 5)]
    >>> sorted(execution_rebalance_sessions(sessions, "W"))
    [datetime.date(2024, 2, 2)]
    >>> sorted(execution_rebalance_sessions(sessions, "M"))
    [datetime.date(2024, 1, 31)]
    """

    # Every session
    if rule == "D":
        return set(sessions)

    # Sessions whose next session starts a new week or month
    rebalance = set()
    for today, nxt in zip(sessions, sessions[1:]):
        if rule == "W" and today.isocalendar()[:2] != nxt.isocalendar()[:2]:
            rebalance.add(today)
        if rule == "M" and (today.year, today.month) != (nxt.year, nxt.month):
            rebalance.add(today)

    return rebalance
