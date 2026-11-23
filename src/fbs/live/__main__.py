'''
__main__.py - Command line: python -m fbs.live {rebalance,status,performance,halt,flatten} STRATEGY [options].
'''

# %%
# Imports

import argparse
import sys

from fbs.live import runner

# %%
# Command Line

# Command line entry point
def main(argv=None):
    """
    Parse the command line and run one command on one strategy.

    Parameters
    ----------
    argv : list of str
        Command line arguments. sys.argv[1:] if None.

    Returns
    -------
    code : int
        Process exit code: 0 on success, 1 on a failed or blocked run.

    Examples
    --------
    flatten without --yes only prints a warning:

    >>> main(["flatten", "strategy_example"])
    flatten closes every position in this strategy's paper account; re-run with --yes
    1

    A dry-run rebalance, the same as python -m fbs.live rebalance strategy_example:

    >>> main(["rebalance", "strategy_example"])  # doctest: +SKIP
    0
    """

    # One sub-command per action, each taking the strategy folder name
    parser = argparse.ArgumentParser(prog="python -m fbs.live", description="Alpaca paper trading runner")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("rebalance", help="plan orders (dry run by default); --submit sends them")
    p.add_argument("strategy")
    p.add_argument("--submit", action="store_true", help="send market-on-close orders to Alpaca paper")
    p.add_argument("--asof", help="dry run for a past signal session, YYYY-MM-DD")
    p.add_argument("--force", action="store_true", help="run even if today is not a rebalance session")

    p = sub.add_parser("status", help="account, positions and recent orders")
    p.add_argument("strategy")

    p = sub.add_parser("performance", help="live results against the backtest, as a PDF in records/")
    p.add_argument("strategy")
    p.add_argument("--start", help="execution session of the first live trade, YYYY-MM-DD; default from records/")

    p = sub.add_parser("halt", help="cancel all open orders")
    p.add_argument("strategy")

    p = sub.add_parser("flatten", help="cancel open orders and close all positions")
    p.add_argument("strategy")
    p.add_argument("--yes", action="store_true", help="required confirmation")

    args = parser.parse_args(argv)

    # Run the chosen command
    if args.command == "rebalance":
        code = runner.rebalance(args.strategy, submit=args.submit,
                                asof=runner.parse_date(args.asof), force=args.force)
    elif args.command == "status":
        code = runner.status(args.strategy)
    elif args.command == "performance":
        code = runner.performance(args.strategy, start=runner.parse_date(args.start))
    elif args.command == "halt":
        code = runner.halt(args.strategy)
    elif args.yes:
        code = runner.halt(args.strategy, flatten=True)
    else:
        print("flatten closes every position in this strategy's paper account; re-run with --yes")
        code = 1

    return code


if __name__ == "__main__":
    sys.exit(main())
