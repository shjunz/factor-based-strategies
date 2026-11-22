'''
report.py - The two PDF reports of a strategy, both written to records/.

Run report      every rebalance run -> records/{exec_session}-{dryrun|rebalance}.pdf
                Run summary, checks, target weights, planned orders and a
                backtest, the same layout for a dry run and a --submit run.
                Before going live the researcher reads the dry-run one to
                decide whether the strategy can go live; after, the
                rebalance one shows what each run decided.
Live report     performance after --submit runs -> records/{last_session}-performance.pdf
                After going live: paper results against the backtest of the
                same sessions, and fill quality. The researcher reads it to
                judge live results and decide how to revise the strategy.

Backtest timing matches the runner: weights of signal session t are bought at
the close of t+1 (market-on-close), so they earn returns from session t+2 on.
Weights are refreshed only on the config.yaml rebalance sessions and held in
between (no intra-period drift, no costs). Returns come from the fetch output,
so the backtest needs fetch to return prices.

Live daily return  = change in account equity / config.yaml paper.capital. One Alpaca
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

from fbs.backtesting import BARS_PER_YEAR, backtest, metrics, split_segments  # noqa: E402,F401

# %%
# Constants

# Page size in inches
A4 = (8.27, 11.69)

# Most recent orders listed in the live report's execution table
MAX_ORDER_ROWS = 28

# %%
# Shared: tables


# Table on an axis
def _table(ax, rows, header, title, col_widths=None):
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
    >>> _table(ax, [["SPY", "50.00%"]], ["Symbol", "Weight"], "Target weights")
    >>> len(ax.tables), ax.get_title(loc="left")
    (1, 'Target weights')
    >>> fig, ax = plt.subplots()
    >>> _table(ax, [], ["Checks"], "Checks")
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
# Dry-run report: before going live

# Run report page 1: run summary
def _run_summary_page(pdf, strategy, record):
    """
    Page 1: run summary, checks, target weights and planned orders.

    Parameters
    ----------
    pdf : PdfPages
        Open PDF.
    strategy : Strategy
        The loaded strategy.
    record : dict
        The run record written by runner.

    Returns
    -------
    None

    Examples
    --------
    >>> import tempfile
    >>> from pathlib import Path
    >>> from fbs.live.loader import load_strategy
    >>> strategy = load_strategy("strategy_example")
    >>> record = {"mode": "dryrun", "signal_session": "2024-12-30",
    ...           "exec_session": "2024-12-31", "run_at": "2024-12-31T15:00:00+00:00",
    ...           "status": "planned", "turnover": 0.26, "failures": [], "notes": [],
    ...           "targets": {"SPY": 0.5, "QQQ": 0.5},
    ...           "orders": [{"side": "buy", "symbol": "QQQ", "qty": 125, "reason": "open"}]}
    >>> with PdfPages(Path(tempfile.mkdtemp()) / "run.pdf") as pdf:
    ...     _run_summary_page(pdf, strategy, record)
    ...     pdf.get_pagecount()
    1
    """

    fig = plt.figure(figsize=A4)
    cfg, paper = strategy.config, strategy.paper

    # Title and run information
    kind = "rebalance" if record["mode"] == "submit" else "dry run"
    fig.text(0.06, 0.95, f"{strategy.name} - {kind} report", fontsize=16, fontweight="bold")
    info = [
        f"Signal session: {record['signal_session']}    Execution: close of {record['exec_session']}",
        f"Run at: {record['run_at'][:19]}    Status: {record['status']}",
        f"Universe: {len(cfg['universe'])} symbols    Rebalance: {cfg['rebalance']}    "
        f"Lookback: {cfg['lookback_sessions']} sessions",
        f"Params: {cfg['params']}",
        f"Split: IS to {cfg['split']['is_end']}, embargo {cfg['split']['embargo_sessions']} sessions, OOS after"
        if cfg.get("split") else "Split: none (full-period backtest only)",
        f"Capital: {float(paper['capital']):,.0f} USD    enabled: {paper['enabled']}    "
        f"Turnover: {record.get('turnover', 'n/a')}",
    ]
    if record["mode"] == "submit":
        sent = record["submitted"]
        rejected = sum(1 for x in sent if x["status"].startswith("rejected"))
        info.append(f"Submitted: {len(sent)} orders    Rejected: {rejected}")
    for i, line in enumerate(info):
        fig.text(0.06, 0.915 - i * 0.022, line, fontsize=9)

    # Checks and notes
    checks = [[f] for f in record["failures"]] or [["all pre-trade checks passed"]]
    checks += [[f"note: {n}"] for n in record["notes"]]
    _table(fig.add_axes([0.06, 0.70, 0.88, 0.09]), checks, ["Checks"], "Checks")

    # Target weights, largest first
    targets = sorted(record["targets"].items(), key=lambda kv: -abs(kv[1]))
    _table(fig.add_axes([0.06, 0.06, 0.38, 0.60]),
           [[s, f"{w:.2%}"] for s, w in targets], ["Symbol", "Weight"],
           f"Target weights ({len(targets)}, gross {sum(abs(w) for _, w in targets):.1%})")

    # Planned orders
    orders = [[o["side"], o["symbol"], o["qty"], o["reason"]] for o in record["orders"]]
    _table(fig.add_axes([0.50, 0.06, 0.44, 0.60]), orders, ["Side", "Symbol", "Qty", "Reason"],
           f"Planned orders ({len(orders)})")

    pdf.savefig(fig)
    plt.close(fig)

# Dry-run page 2: backtest
def _dry_run_backtest_page(pdf, bt, rule, split):
    """
    Page 2: equity curves, drawdown and a performance table per segment.
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
    ...     _dry_run_backtest_page(pdf, bt, "M",
    ...                            {"is_end": "2023-02-15", "embargo_sessions": 5})
    ...     pdf.get_pagecount()
    1
    """

    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=A4, gridspec_kw={"height_ratios": [3, 1.3, 1.6]})
    fig.suptitle(f"Backtest {bt.index[0].date()} to {bt.index[-1].date()} "
                 f"(rebalance {rule}, MOC at t+1, no costs)", fontsize=12, fontweight="bold")
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
    _table(ax3, rows, ["Segment", "", "Annual return", "Annual vol", "Sharpe", "Max drawdown", "Turnover / yr"],
           "Performance" + (f" (OOS is report only; embargo {split['embargo_sessions']} sessions not evaluated)"
                            if split else ""),
           col_widths=[0.30, 0.12, 0.12, 0.11, 0.08, 0.14, 0.13])

    fig.tight_layout(rect=(0, 0, 1, 0.97))
    pdf.savefig(fig)
    plt.close(fig)

# Run report PDF
def write_run_report(path, strategy, record, prices, weights):
    """
    Write the run report PDF of a dry run or a --submit run: the summary page,
    then the backtest page when there is enough data.

    Parameters
    ----------
    path : Path
        Destination .pdf file.
    strategy : Strategy
        The loaded strategy.
    record : dict
        The run record written by runner.
    prices : pd.DataFrame or None
        Prices from data.fetch. None if the run was blocked before fetching.
    weights : pd.DataFrame or None
        Weights from weights.compute. None if the run was blocked before computing them.

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
    >>> record = {"mode": "dryrun", "signal_session": "2024-12-30",
    ...           "exec_session": "2024-12-31", "run_at": "2024-12-31T15:00:00+00:00",
    ...           "status": "planned", "turnover": 0.26, "failures": [], "notes": [],
    ...           "targets": {"SPY": 0.5, "QQQ": 0.5},
    ...           "orders": [{"side": "buy", "symbol": "QQQ", "qty": 125, "reason": "open"}]}
    >>> folder = Path(tempfile.mkdtemp())

    A run blocked before fetching has the summary page only:

    >>> write_run_report(folder / "2024-12-31-dryrun.pdf", strategy, record, None, None).name
    '2024-12-31-dryrun.pdf'

    With prices and weights, the backtest page follows:

    >>> idx = pd.bdate_range("2024-10-01", periods=60)
    >>> prices = pd.DataFrame({"SPY": np.linspace(570, 590, 60),
    ...                        "QQQ": np.linspace(490, 515, 60)}, index=idx)
    >>> weights = pd.DataFrame(0.5, index=idx, columns=prices.columns)
    >>> write_run_report(folder / "2024-12-31-rebalance.pdf", strategy, record,
    ...                  prices, weights).exists()
    True
    """

    rule = strategy.config["rebalance"]
    with PdfPages(path) as pdf:
        _run_summary_page(pdf, strategy, record)
        if prices is not None and weights is not None:
            bt = backtest(prices, weights, rule)
            if len(bt) > 1:
                _dry_run_backtest_page(pdf, bt, rule, strategy.config.get("split"))

    return path

# %%
# Live report: after going live

# Fill quality of each order
def executions(orders, closes, name):
    """
    One row per order: what was asked, what was filled, and the fill price
    against the session close.

    Parameters
    ----------
    orders : list of alpaca Order
        This strategy's orders.
    closes : pd.DataFrame
        Output of AlpacaBroker.daily_closes.
    name : str
        Strategy name, the client_order_id prefix.

    Returns
    -------
    ex : pd.DataFrame
        Columns = session, symbol, side, qty, filled_qty, fill, close,
        notional, slippage_bps, status. slippage_bps > 0 means the fill was
        worse than the close.

    Examples
    --------
    >>> from types import SimpleNamespace as Order
    >>> orders = [Order(client_order_id="demo-2024-12-31-SPY-open", side="buy",
    ...                 symbol="SPY", qty="10", filled_qty="10",
    ...                 filled_avg_price="586.37", status="filled"),
    ...           Order(client_order_id="demo-2024-12-31-QQQ-open", side="sell",
    ...                 symbol="QQQ", qty="5", filled_qty="0",
    ...                 filled_avg_price=None, status="canceled")]
    >>> closes = pd.DataFrame({"SPY": [586.08], "QQQ": [511.23]},
    ...                       index=pd.to_datetime(["2024-12-31"]))
    >>> ex = executions(orders, closes, "demo")
    >>> ex[["symbol", "side", "fill", "close", "slippage_bps", "status"]].round(2)
      symbol  side    fill   close  slippage_bps    status
    0    SPY   buy  586.37  586.08          4.95    filled
    1    QQQ  sell     NaN  511.23           NaN  canceled
    """

    rows = []
    for o in orders:
        session = pd.Timestamp(o.client_order_id[len(name) + 1:len(name) + 11])
        side = str(getattr(o.side, "value", o.side)).lower()
        fill = float(o.filled_avg_price) if o.filled_avg_price else np.nan
        filled = float(o.filled_qty or 0)
        close = closes[o.symbol].get(session, np.nan) if o.symbol in closes else np.nan
        sign = 1 if side == "buy" else -1
        rows.append({
            "session": session, "symbol": o.symbol, "side": side,
            "qty": float(o.qty or 0), "filled_qty": filled, "fill": fill, "close": close,
            "notional": filled * fill if filled else 0.0,
            "slippage_bps": sign * (fill / close - 1) * 1e4,
            "status": str(getattr(o.status, "value", o.status)),
        })
    ex = pd.DataFrame(rows, columns=["session", "symbol", "side", "qty", "filled_qty", "fill", "close",
                                     "notional", "slippage_bps", "status"])

    return ex

# Execution summary
def execution_summary(ex):
    """
    Order counts, fill rate and notional-weighted slippage.

    Parameters
    ----------
    ex : pd.DataFrame
        Output of executions.

    Returns
    -------
    s : dict
        orders, filled, not_filled, fill_rate, slippage_bps, slippage_usd.

    Examples
    --------
    >>> from types import SimpleNamespace as Order
    >>> orders = [Order(client_order_id="demo-2024-12-31-SPY-open", side="buy",
    ...                 symbol="SPY", qty="10", filled_qty="10",
    ...                 filled_avg_price="586.37", status="filled"),
    ...           Order(client_order_id="demo-2024-12-31-QQQ-open", side="sell",
    ...                 symbol="QQQ", qty="5", filled_qty="0",
    ...                 filled_avg_price=None, status="canceled")]
    >>> closes = pd.DataFrame({"SPY": [586.08], "QQQ": [511.23]},
    ...                       index=pd.to_datetime(["2024-12-31"]))
    >>> s = execution_summary(executions(orders, closes, "demo"))
    >>> {k: round(float(v), 2) for k, v in s.items()}
    {'orders': 2.0, 'filled': 1.0, 'not_filled': 1.0, 'fill_rate': 0.67, 'slippage_bps': 4.95, 'slippage_usd': 2.9}
    """

    priced = ex[ex["filled_qty"] > 0].dropna(subset=["slippage_bps"])
    weight = priced["notional"].sum()
    s = {
        "orders": len(ex),
        "filled": int((ex["filled_qty"] >= ex["qty"]).sum()),
        "not_filled": int((ex["filled_qty"] < ex["qty"]).sum()),
        "fill_rate": ex["filled_qty"].sum() / ex["qty"].sum() if ex["qty"].sum() else np.nan,
        "slippage_bps": (priced["slippage_bps"] * priced["notional"]).sum() / weight if weight else np.nan,
        "slippage_usd": (priced["slippage_bps"] / 1e4 * priced["notional"]).sum(),
    }

    return s

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
    _table(fig.add_axes([0.06, 0.72, 0.88, 0.10]), rows,
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
        Output of executions.
    summary : dict
        Output of execution_summary.

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
    >>> ex = executions(orders, closes, "demo")
    >>> with PdfPages(Path(tempfile.mkdtemp()) / "live.pdf") as pdf:
    ...     _live_execution_page(pdf, cmp, ex, execution_summary(ex))
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
    _table(fig.add_axes([0.06, 0.04, 0.88, 0.52]), rows,
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
        Output of executions.

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
    >>> path = Path(tempfile.mkdtemp()) / "2024-12-31-performance.pdf"
    >>> write_live_report(path, strategy, ["Live since 2024-12-02"], cmp,
    ...                   executions(orders, closes, "demo")).name
    '2024-12-31-performance.pdf'
    """

    with PdfPages(path) as pdf:
        _live_returns_page(pdf, strategy, info, cmp)
        _live_execution_page(pdf, cmp, ex, execution_summary(ex))

    return path
