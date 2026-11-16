"""PDF report for one dry run: run summary, checks, target weights, planned orders and a backtest.

Backtest timing matches the runner: weights of signal session t are bought at the close of t+1
(market-on-close), so they earn returns from session t+2 on. Weights are refreshed only on the
config.yaml rebalance sessions and held in between (no intra-period drift, no costs).
Returns are taken from the fetch output, so the backtest needs fetch to return prices.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402

from fbs.live.plan import rebalance_sessions  # noqa: E402

BARS_PER_YEAR = 252
A4 = (8.27, 11.69)


def backtest(prices: pd.DataFrame, weights: pd.DataFrame, rule: str) -> pd.DataFrame:
    """Daily strategy and equal-weight benchmark returns, plus one-way turnover per session."""
    rets = prices.astype(float).pct_change(fill_method=None)
    sessions = list(weights.index.date)
    is_rebalance = pd.Series(weights.index.date, index=weights.index).isin(rebalance_sessions(sessions, rule))
    held = weights.where(is_rebalance, axis=0).ffill().fillna(0.0).reindex(columns=rets.columns, fill_value=0.0)

    out = pd.DataFrame({
        "strategy": (held.shift(2) * rets.fillna(0.0)).sum(axis=1),
        "benchmark": rets.mean(axis=1),
        "turnover": held.diff().abs().sum(axis=1).shift(1) / 2,
    })
    invested = held.abs().sum(axis=1) > 0
    if not invested.any():
        return out.iloc[0:0]
    return out.loc[invested.idxmax():].iloc[2:].fillna(0.0)


def metrics(r: pd.Series) -> dict[str, float]:
    if len(r) < 2 or r.std() == 0:
        return {"Annual return": np.nan, "Annual vol": np.nan, "Sharpe": np.nan, "Max drawdown": np.nan}
    equity = (1 + r).cumprod()
    return {
        "Annual return": equity.iloc[-1] ** (BARS_PER_YEAR / len(r)) - 1,
        "Annual vol": r.std() * np.sqrt(BARS_PER_YEAR),
        "Sharpe": r.mean() / r.std() * np.sqrt(BARS_PER_YEAR),
        "Max drawdown": (equity / equity.cummax() - 1).min(),
    }


def _table(ax, rows: list[list], header: list[str], title: str) -> None:
    ax.axis("off")
    ax.set_title(title, loc="left", fontsize=11, fontweight="bold")
    if not rows:
        ax.text(0, 0.9, "none", fontsize=9, transform=ax.transAxes)
        return
    t = ax.table(cellText=rows, colLabels=header, loc="upper left", cellLoc="left", colLoc="left")
    t.auto_set_font_size(False)
    t.set_fontsize(8)
    t.scale(1, 1.25)


def _summary_page(pdf: PdfPages, strategy, record: dict) -> None:
    fig = plt.figure(figsize=A4)
    fig.text(0.06, 0.95, f"{strategy.name} - dry run report", fontsize=16, fontweight="bold")
    cfg, paper = strategy.config, strategy.paper
    info = [
        f"Signal session: {record['signal_session']}    Execution: close of {record['exec_session']}",
        f"Run at: {record['run_at'][:19]}    Git: {record['git']}    Status: {record['status']}",
        f"Universe: {len(cfg['universe'])} symbols    Rebalance: {cfg['rebalance']}    "
        f"Lookback: {cfg['lookback_sessions']} sessions",
        f"Params: {cfg['params']}",
        f"Capital: {float(paper['capital']):,.0f} USD    enabled: {paper['enabled']}    "
        f"Turnover: {record.get('turnover', 'n/a')}",
    ]
    for i, line in enumerate(info):
        fig.text(0.06, 0.915 - i * 0.022, line, fontsize=9)

    checks = [[f] for f in record["failures"]] or [["all pre-trade checks passed"]]
    checks += [[f"note: {n}"] for n in record["notes"]]
    _table(fig.add_axes([0.06, 0.70, 0.88, 0.09]), checks, ["Checks"], "Checks")

    targets = sorted(record["targets"].items(), key=lambda kv: -abs(kv[1]))
    _table(fig.add_axes([0.06, 0.06, 0.38, 0.60]),
           [[s, f"{w:.2%}"] for s, w in targets], ["Symbol", "Weight"],
           f"Target weights ({len(targets)}, gross {sum(abs(w) for _, w in targets):.1%})")
    orders = [[o["side"], o["symbol"], o["qty"], o["reason"]] for o in record["orders"]]
    _table(fig.add_axes([0.50, 0.06, 0.44, 0.60]), orders, ["Side", "Symbol", "Qty", "Reason"],
           f"Planned orders ({len(orders)})")
    pdf.savefig(fig)
    plt.close(fig)


def _backtest_page(pdf: PdfPages, bt: pd.DataFrame, rule: str) -> None:
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=A4, gridspec_kw={"height_ratios": [3, 1.3, 1.6]})
    fig.suptitle(f"Backtest {bt.index[0].date()} to {bt.index[-1].date()} "
                 f"(rebalance {rule}, MOC at t+1, no costs)", fontsize=12, fontweight="bold")
    equity = (1 + bt[["strategy", "benchmark"]]).cumprod()
    equity.plot(ax=ax1, lw=1.2)
    ax1.set_ylabel("Growth of 1")
    ax1.legend(["Strategy", "Equal-weight universe"], fontsize=8)
    ax1.grid(alpha=0.3)

    dd = equity["strategy"] / equity["strategy"].cummax() - 1
    ax2.fill_between(dd.index, dd.values, 0, color="tab:red", alpha=0.4)
    ax2.set_ylabel("Drawdown")
    ax2.grid(alpha=0.3)

    years = len(bt) / BARS_PER_YEAR
    rows = []
    for col in ("strategy", "benchmark"):
        m = metrics(bt[col])
        rows.append([col.capitalize(), *(f"{v:.2f}" if k == "Sharpe" else f"{v:.2%}" for k, v in m.items())])
    rows[0].append(f"{bt['turnover'].sum() / years:.2f}")
    rows[1].append("-")
    _table(ax3, rows, ["", "Annual return", "Annual vol", "Sharpe", "Max drawdown", "Turnover / yr"],
           "Performance")
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    pdf.savefig(fig)
    plt.close(fig)


def write_report(path: Path, strategy, record: dict, prices: pd.DataFrame | None,
                 weights: pd.DataFrame | None) -> Path:
    """Write the PDF. prices/weights are None when the run was blocked before computing them."""
    with PdfPages(path) as pdf:
        _summary_page(pdf, strategy, record)
        if prices is not None and weights is not None:
            bt = backtest(prices, weights, strategy.config["rebalance"])
            if len(bt) > 1:
                _backtest_page(pdf, bt, strategy.config["rebalance"])
    return path
