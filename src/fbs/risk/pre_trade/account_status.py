'''
account_status.py - risk_account: the broker account is active, not blocked
and holds the strategy's capital.
'''

# %%
# Checks

# Account check
def risk_account(account, capital):
    """
    Check the account is active, not blocked, and holds the strategy's capital.

    Parameters
    ----------
    account : AccountState
        Current account summary.
    capital : float
        config.yaml paper.capital in USD.

    Returns
    -------
    failures : list of str
        Empty if the account can trade.

    Examples
    --------
    >>> from fbs.live.brokers import AccountState
    >>> ok = AccountState(equity=100_000, buying_power=200_000, active=True,
    ...                   trading_blocked=False, account_blocked=False, status="ACTIVE")
    >>> risk_account(ok, capital=50_000)
    []
    >>> closed = AccountState(equity=40_000, buying_power=80_000, active=False,
    ...                       trading_blocked=True, account_blocked=False, status="ACCOUNT_CLOSED")
    >>> risk_account(closed, capital=50_000)
    ['account status ACCOUNT_CLOSED', 'account is blocked', 'capital 50,000 > account equity 40,000']
    """

    failures = []
    if not account.active:
        failures.append(f"account status {account.status}")
    if account.trading_blocked or account.account_blocked:
        failures.append("account is blocked")
    if capital > account.equity:
        failures.append(f"capital {capital:,.0f} > account equity {account.equity:,.0f}")

    return failures
