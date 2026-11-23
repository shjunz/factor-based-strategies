'''
live_report.py - The live report PDF, written after the close by the
`performance` command: records/{last_session}-live-trading.pdf.

Page 1  live returns against the backtest of the same sessions and the
        equal-weight universe: metrics, growth of 1, live drawdown.
Page 2  cumulative live minus backtest, fill summary, most recent orders.

Live daily return  = change in account equity / config.yaml paper.capital. One broker
                     paper account per strategy, so the account is the strategy.
                     Deposits or resets of the paper account show up as returns.
Execution          = each order's fill price against the session's
                     unadjusted SIP close; a MOC fill should be the close.
'''

# %%
# Imports

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402

from fbs.backtesting import BARS_PER_YEAR, metrics  # noqa: E402
from fbs.backtesting.backtest_report import A4, pdf_table  # noqa: E402
from fbs.risk.post_trade.fills import risk_fill_summary, risk_fills  # noqa: E402,F401

# %%
# Constants

# Most recent orders listed in the live report's execution table
MAX_ORDER_ROWS = 28

# %%
# Live report

# Live page 1: live against backtest
def _live_returns_page(pdf, strategy, info, cmp):
    """
    Page 1: run information, metrics table, growth curves and live drawdown.

    Parameters
    ----------
    pdf : PdfPages
        Open PDF.
    strategy : Strategy
        The loaded strategy.
    info : list of str
        Header lines.
    cmp : pd.DataFrame
        Output of compare.

    Returns
    -------
    None

    Examples
    --------
    >>> import tempfile
    >>> from pathlib import Path
    >>> from fbs.live.loader import load_strategy
    >>> strategy = load_strategy("strategy_example")
    >>> rng = np.random.default_rng(0)
    >>> cmp = pd.DataFrame(rng.normal(0.0005, 0.01, (20, 3)),
    ...                    index=pd.bdate_range("2024-12-02", periods=20),
    ...                    columns=["live", "backtest", "benchmark"])
    >>> with PdfPages(Path(tempfile.mkdtemp()) / "live.pdf") as pdf:
    ...     _live_returns_page(pdf, strategy, ["Live since 2024-12-02"], cmp)
    ...     pdf.get_pagecount()
    1
    """

    fig = plt.figure(figsize=A4)
    fig.text(0.06, 0.95, f"{strategy.name} - live performance", fontsize=16, fontweight="bold")
    for i, line in enumerate(info):
        fig.text(0.06, 0.915 - i * 0.022, line, fontsize=9)

    # Metrics, with tracking error and correlation of live against the backtest
    gap = cmp["live"] - cmp["backtest"]
    rows = []
    for col, label in (("live", "Live"), ("backtest", "Backtest"), ("benchmark", "Equal-weight")):
        m = metrics(cmp[col])
        cum = (1 + cmp[col]).prod() - 1
        rows.append([label, f"{cum:.2%}", *(f"{v:.2f}" if k == "Sharpe" else f"{v:.2%}" for k, v in m.items())])
    pdf_table(fig.add_axes([0.06, 0.72, 0.88, 0.10]), rows,
           ["", "Cumulative", "Annual return", "Annual vol", "Sharpe", "Max drawdown"],
           f"Performance, {len(cmp)} sessions    tracking error {gap.std() * np.sqrt(BARS_PER_YEAR):.2%}"
           f"    correlation {cmp['live'].corr(cmp['backtest']):.2f}")

    # Growth of 1
    ax1 = fig.add_axes([0.10, 0.36, 0.84, 0.30])
    growth = (1 + cmp).cumprod()
    growth.plot(ax=ax1, lw=1.2)
    ax1.set_ylabel("Growth of 1")
    ax1.legend(["Live", "Backtest", "Equal-weight universe"], fontsize=8)
    ax1.grid(alpha=0.3)

    # Live drawdown
    ax2 = fig.add_axes([0.10, 0.08, 0.84, 0.20])
    dd = growth["live"] / growth["live"].cummax() - 1
    ax2.fill_between(dd.index, dd.values, 0, color="tab:red", alpha=0.4)
    ax2.set_ylabel("Live drawdown")
    ax2.grid(alpha=0.3)

    pdf.savefig(fig)
    plt.close(fig)

# Live page 2: tracking and execution
def _live_execution_page(pdf, cmp, ex, summary):
    """
    Page 2: cumulative live minus backtest, execution summary and the most
    recent orders.

    Parameters
    ----------
    pdf : PdfPages
        Open PDF.
    cmp : pd.DataFrame
        Output of compare.
    ex : pd.DataFrame
        Output of risk_fills.
    summary : dict
        Output of risk_fill_summary.

    Returns
    -------
    None

    Examples
    --------
    >>> import tempfile
    >>> from pathlib import Path
    >>> rng = np.random.default_rng(0)
    >>> cmp = pd.DataFrame(rng.normal(0.0005, 0.01, (20, 3)),
    ...                    index=pd.bdate_range("2024-12-02", periods=20),
    ...                    columns=["live", "backtest", "benchmark"])
    >>> from types import SimpleNamespace as Order
    >>> orders = [Order(client_order_id="demo-2024-12-31-SPY-open", side="buy",
    ...                 symbol="SPY", qty="10", filled_qty="10",
    ...                 filled_avg_price="586.37", status="filled"),
    ...           Order(client_order_id="demo-2024-12-31-QQQ-open", side="sell",
    ...                 symbol="QQQ", qty="5", filled_qty="0",
    ...                 filled_avg_price=None, status="canceled")]
    >>> closes = pd.DataFrame({"SPY": [586.08], "QQQ": [511.23]},
    ...                       index=pd.to_datetime(["2024-12-31"]))
    >>> ex = risk_fills(orders, closes, "demo")
    >>> with PdfPages(Path(tempfile.mkdtemp()) / "live.pdf") as pdf:
    ...     _live_execution_page(pdf, cmp, ex, risk_fill_summary(ex))
    ...     pdf.get_pagecount()
    1
    """

    fig = plt.figure(figsize=A4)
    fig.text(0.06, 0.95, "Tracking and execution", fontsize=14, fontweight="bold")

    # Cumulative return gap: where live and backtest part ways
    ax = fig.add_axes([0.13, 0.72, 0.81, 0.20])
    ((1 + cmp["live"]).cumprod() - (1 + cmp["backtest"]).cumprod()).plot(ax=ax, lw=1.2, color="tab:purple")
    ax.axhline(0, color="grey", lw=0.8)
    ax.set_ylabel("Live - backtest\n(growth of 1)")
    ax.grid(alpha=0.3)

    # Summary
    lines = [
        f"Orders {summary['orders']}    fully filled {summary['filled']}    not fully filled "
        f"{summary['not_filled']}    fill rate {summary['fill_rate']:.1%} of shares",
        f"Slippage against the close: {summary['slippage_bps']:.1f} bps notional-weighted, "
        f"{summary['slippage_usd']:,.0f} USD in total (positive = cost)",
    ]
    for i, line in enumerate(lines):
        fig.text(0.06, 0.62 - i * 0.022, line, fontsize=9)

    # Most recent orders
    recent = ex.sort_values("session").tail(MAX_ORDER_ROWS).iloc[::-1]
    rows = [[r.session.date(), r.symbol, r.side, f"{r.filled_qty:g}/{r.qty:g}",
             "-" if np.isnan(r.fill) else f"{r.fill:.2f}", "-" if np.isnan(r.close) else f"{r.close:.2f}",
             "-" if np.isnan(r.slippage_bps) else f"{r.slippage_bps:.1f}", r.status]
            for r in recent.itertuples()]
    pdf_table(fig.add_axes([0.06, 0.04, 0.88, 0.52]), rows,
           ["Session", "Symbol", "Side", "Filled", "Fill", "Close", "Slip bps", "Status"],
           f"Most recent orders ({len(recent)} of {len(ex)})")

    pdf.savefig(fig)
    plt.close(fig)

# Live PDF
def write_live_report(path, strategy, info, cmp, ex):
    """
    Write the live performance PDF.

    Parameters
    ----------
    path : Path
        Destination .pdf file.
    strategy : Strategy
        The loaded strategy.
    info : list of str
        Header lines for page 1.
    cmp : pd.DataFrame
        Output of compare.
    ex : pd.DataFrame
        Output of risk_fills.

    Returns
    -------
    path : Path
        The written file.

    Examples
    --------
    >>> import tempfile
    >>> from pathlib import Path
    >>> from fbs.live.loader import load_strategy
    >>> strategy = load_strategy("strategy_example")
    >>> rng = np.random.default_rng(0)
    >>> cmp = pd.DataFrame(rng.normal(0.0005, 0.01, (20, 3)),
    ...                    index=pd.bdate_range("2024-12-02", periods=20),
    ...                    columns=["live", "backtest", "benchmark"])
    >>> from types import SimpleNamespace as Order
    >>> orders = [Order(client_order_id="demo-2024-12-31-SPY-open", side="buy",
    ...                 symbol="SPY", qty="10", filled_qty="10",
    ...                 filled_avg_price="586.37", status="filled"),
    ...           Order(client_order_id="demo-2024-12-31-QQQ-open", side="sell",
    ...                 symbol="QQQ", qty="5", filled_qty="0",
    ...                 filled_avg_price=None, status="canceled")]
    >>> closes = pd.DataFrame({"SPY": [586.08], "QQQ": [511.23]},
    ...                       index=pd.to_datetime(["2024-12-31"]))
    >>> path = Path(tempfile.mkdtemp()) / "2024-12-31-live-trading.pdf"
    >>> write_live_report(path, strategy, ["Live since 2024-12-02"], cmp,
    ...                   risk_fills(orders, closes, "demo")).name
    '2024-12-31-live-trading.pdf'
    """

    with PdfPages(path) as pdf:
        _live_returns_page(pdf, strategy, info, cmp)
        _live_execution_page(pdf, cmp, ex, risk_fill_summary(ex))

    return path
