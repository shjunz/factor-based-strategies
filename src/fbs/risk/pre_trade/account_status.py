'''
account_status.py - risk_account: the Alpaca account is active, not blocked
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
    """

    failures = []
    if not account.status.upper().endswith("ACTIVE"):
        failures.append(f"account status {account.status}")
    if account.trading_blocked or account.account_blocked:
        failures.append("account is blocked")
    if capital > account.equity:
        failures.append(f"capital {capital:,.0f} > account equity {account.equity:,.0f}")

    return failures
