'''
backtest_report.py - The backtest report PDF, written by every rebalance run
before any check or order. The same report for a dry run and a --submit
run; the name carries the backtest's IS / OOS dates, so backtests with a
different split sit side by side:

    records/{exec_session}-backtest_IS-{first}-{last}_OOS-{first}-{last}.pdf
    records/{exec_session}-backtest_FULL-{first}-{last}.pdf        (no split)

One page: equity curves of the strategy and the equal-weight universe,
strategy drawdown, and a performance table per segment (IS / OOS when
config.yaml has a split). It shows only the historical backtest; today's
targets, checks and orders are in the rebalance JSON next to it.

Also holds pdf_table and A4, shared with the live report in
fbs.risk.post_trade.live_report.
'''

# %%
# Imports

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402

from fbs.backtesting.performance_metrics import BARS_PER_YEAR, metrics  # noqa: E402
from fbs.backtesting.sample_split import split_segments  # noqa: E402

# %%
# Constants

# Page size in inches
A4 = (8.27, 11.69)

# %%
# Tables

# Table on an axis
def pdf_table(ax, rows, header, title, col_widths=None):
    """
    Draw a table with a title on an axis, or "none" if there are no rows.

    Parameters
    ----------
    ax : matplotlib Axes
        Axis to draw on.
    rows : list of list
        Table cells.
    header : list of str
        Column labels.
    title : str
        Title above the table.
    col_widths : list of float, optional
        Column widths as fractions of the axis width; equal widths if None.

    Returns
    -------
    None

    Examples
    --------
    >>> fig, ax = plt.subplots()
    >>> pdf_table(ax, [["SPY", "50.00%"]], ["Symbol", "Weight"], "Target weights")
    >>> len(ax.tables), ax.get_title(loc="left")
    (1, 'Target weights')
    >>> fig, ax = plt.subplots()
    >>> pdf_table(ax, [], ["Checks"], "Checks")
    >>> [t.get_text() for t in ax.texts]
    ['none']
    """

    ax.axis("off")
    ax.set_title(title, loc="left", fontsize=11, fontweight="bold")
    if not rows:
        ax.text(0, 0.9, "none", fontsize=9, transform=ax.transAxes)
        return
    t = ax.table(cellText=rows, colLabels=header, loc="upper left", cellLoc="left", colLoc="left",
                 colWidths=col_widths)
    t.auto_set_font_size(False)
    t.set_fontsize(8)
    t.scale(1, 1.25)


# %%
# Backtest report

# Backtest report page
def _backtest_page(pdf, bt, rule, split, name):
    """
    The one page: equity curves, drawdown and a performance table per segment.
    With a config.yaml split, the Embargo and OOS spans are shaded and the
    table has one row per segment (IS, OOS) instead of the full period.

    Parameters
    ----------
    pdf : PdfPages
        Open PDF.
    bt : pd.DataFrame
        Output of backtest.
    rule : str
        config.yaml rebalance, for the title.
    split : dict or None
        config.yaml split, None for no split.
    name : str
        Strategy name, for the title.

    Returns
    -------
    None

    Examples
    --------
    >>> import tempfile
    >>> from pathlib import Path
    >>> rng = np.random.default_rng(0)
    >>> bt = pd.DataFrame({"strategy": rng.normal(0.0005, 0.01, 60),
    ...                    "benchmark": rng.normal(0.0003, 0.01, 60), "turnover": 0.0},
    ...                   index=pd.bdate_range("2023-01-02", periods=60))
    >>> with PdfPages(Path(tempfile.mkdtemp()) / "backtest.pdf") as pdf:
    ...     _backtest_page(pdf, bt, "M", {"is_end": "2023-02-15", "embargo_sessions": 5}, "demo")
    ...     pdf.get_pagecount()
    1
    """

    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=A4, gridspec_kw={"height_ratios": [3, 1.3, 1.6]})
    fig.suptitle(f"{name} - backtest {bt.index[0].date()} to {bt.index[-1].date()}\n"
                 f"rebalance {rule}, MOC at t+1, no costs", fontsize=12, fontweight="bold")
    segments = split_segments(bt, split)

    # Equity curves
    equity = (1 + bt[["strategy", "benchmark"]]).cumprod()
    equity.rename(columns={"strategy": "Strategy", "benchmark": "Equal-weight universe"}).plot(ax=ax1, lw=1.2)
    ax1.set_ylabel("Growth of 1")
    ax1.grid(alpha=0.3)

    # Strategy drawdown
    dd = equity["strategy"] / equity["strategy"].cummax() - 1
    ax2.fill_between(dd.index, dd.values, 0, color="tab:red", alpha=0.4)
    ax2.set_ylabel("Drawdown")
    ax2.grid(alpha=0.3)

    # Shade Embargo and OOS on both charts
    for name, color in (("Embargo", "tab:gray"), ("OOS", "tab:orange")):
        dates = segments.index[segments == name]
        if len(dates):
            for ax in (ax1, ax2):
                ax.axvspan(dates[0], dates[-1], color=color, alpha=0.12, lw=0,
                           label=name if ax is ax1 else None)
    ax1.legend(fontsize=8)

    # Performance table: one row per segment and series; Embargo is not evaluated
    rows = []
    for seg in [s for s in ("Full", "IS", "OOS") if (segments == s).any()]:
        part = bt[segments == seg]
        label = f"{seg} {part.index[0].date()} to {part.index[-1].date()}"
        for col in ("strategy", "benchmark"):
            m = metrics(part[col])
            turnover = f"{part['turnover'].sum() / (len(part) / BARS_PER_YEAR):.2f}" if col == "strategy" else "-"
            rows.append([label if col == "strategy" else "", col.capitalize(),
                         *(f"{v:.2f}" if k == "Sharpe" else f"{v:.2%}" for k, v in m.items()), turnover])
    pdf_table(ax3, rows, ["Segment", "", "Annual return", "Annual vol", "Sharpe", "Max drawdown", "Turnover / yr"],
           "Performance" + (f" (OOS is report only; embargo {split['embargo_sessions']} sessions not evaluated)"
                            if split else ""),
           col_widths=[0.30, 0.12, 0.12, 0.11, 0.08, 0.14, 0.13])

    fig.tight_layout(rect=(0, 0, 1, 0.95))
    pdf.savefig(fig)
    plt.close(fig)

# Backtest report file name
def backtest_report_name(exec_session, bt, split):
    """
    File name of the backtest report, with the first and last session of
    each evaluated segment (IS and OOS, or FULL without a split).

    Parameters
    ----------
    exec_session : str
        Execution session, YYYY-MM-DD.
    bt : pd.DataFrame
        Output of backtest.
    split : dict or None
        config.yaml split, None for no split.

    Returns
    -------
    name : str
        The file name.

    Examples
    --------
    >>> bt = pd.DataFrame({"strategy": 0.0}, index=pd.bdate_range("2026-09-01", "2026-11-19"))
    >>> backtest_report_name("2026-11-20", bt, {"is_end": "2026-09-30", "embargo_sessions": 5})
    '2026-11-20-backtest_IS-20260901-20260930_OOS-20261008-20261119.pdf'
    >>> backtest_report_name("2026-11-20", bt, None)
    '2026-11-20-backtest_FULL-20260901-20261119.pdf'
    """

    segments = split_segments(bt, split)
    spans = []
    for seg in ("Full", "IS", "OOS"):
        days = segments.index[segments == seg]
        if len(days):
            spans.append(f"{seg.upper()}-{days[0]:%Y%m%d}-{days[-1]:%Y%m%d}")
    name = f"{exec_session}-backtest_{'_'.join(spans)}.pdf"

    return name

# Backtest report PDF
def write_backtest_report(path, strategy, bt):
    """
    Write the backtest report PDF.

    Parameters
    ----------
    path : Path
        Destination .pdf file.
    strategy : Strategy
        The loaded strategy.
    bt : pd.DataFrame
        Output of backtest, at least 2 sessions.

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
    >>> bt = pd.DataFrame({"strategy": rng.normal(0.0005, 0.01, 60),
    ...                    "benchmark": rng.normal(0.0003, 0.01, 60), "turnover": 0.0},
    ...                   index=pd.bdate_range("2023-01-02", periods=60))
    >>> write_backtest_report(Path(tempfile.mkdtemp()) / "2024-12-31-backtest_FULL-20230102-20230324.pdf",
    ...                       strategy, bt).name
    '2024-12-31-backtest_FULL-20230102-20230324.pdf'
    """

    with PdfPages(path) as pdf:
        _backtest_page(pdf, bt, strategy.config["rebalance"], strategy.config.get("split"), strategy.name)

    return path
