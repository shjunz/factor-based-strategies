"""Command line: python -m fbs.live {rebalance,status,halt,flatten} STRATEGY [options]."""

from __future__ import annotations

import argparse
import sys

from fbs.live import runner


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m fbs.live", description="Alpaca paper trading runner")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("rebalance", help="plan orders (dry run by default); --submit sends them")
    p.add_argument("strategy")
    p.add_argument("--submit", action="store_true", help="send market-on-close orders to Alpaca paper")
    p.add_argument("--asof", help="dry run for a past signal session, YYYY-MM-DD")
    p.add_argument("--force", action="store_true", help="run even if today is not a rebalance session")

    p = sub.add_parser("status", help="account, positions and recent orders")
    p.add_argument("strategy")

    p = sub.add_parser("halt", help="cancel all open orders")
    p.add_argument("strategy")

    p = sub.add_parser("flatten", help="cancel open orders and close all positions")
    p.add_argument("strategy")
    p.add_argument("--yes", action="store_true", help="required confirmation")

    args = parser.parse_args(argv)
    if args.command == "rebalance":
        return runner.rebalance(args.strategy, submit=args.submit, asof=runner.parse_date(args.asof),
                                force=args.force)
    if args.command == "status":
        return runner.status(args.strategy)
    if args.command == "halt":
        return runner.halt(args.strategy)
    if args.command == "flatten":
        if not args.yes:
            print("flatten closes every position in this strategy's paper account; re-run with --yes")
            return 1
        return runner.halt(args.strategy, flatten=True)
    return 1


if __name__ == "__main__":
    sys.exit(main())
