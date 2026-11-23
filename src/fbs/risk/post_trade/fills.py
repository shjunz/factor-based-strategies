'''
fills.py - Fill reconciliation after the orders were sent: what each order
asked for, what was filled, and the fill price against the session close.
A market-on-close order fills at the close, so this runs after the close
(the `performance` command), never in the --submit run that sent the orders.

risk_fills         one row per order: qty, filled, fill, close, slippage
risk_fill_summary  order counts, fill rate, notional-weighted slippage
'''

# %%
# Imports

import numpy as np
import pandas as pd

# %%
# Fills

# Fill quality of each order
def risk_fills(orders, closes, name):
    """
    One row per order: what was asked, what was filled, and the fill price
    against the session close.

    Parameters
    ----------
    orders : list of OrderRecord
        This strategy's orders, from broker.orders_with_prefix.
    closes : pd.DataFrame
        Output of broker.daily_closes.
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
    >>> ex = risk_fills(orders, closes, "demo")
    >>> ex[["symbol", "side", "fill", "close", "slippage_bps", "status"]].round(2)
      symbol  side    fill   close  slippage_bps    status
    0    SPY   buy  586.37  586.08          4.95    filled
    1    QQQ  sell     NaN  511.23           NaN  canceled
    """

    rows = []
    for o in orders:
        session = pd.Timestamp(o.client_order_id[len(name) + 1:len(name) + 11])
        side = str(o.side).lower()
        fill = float(o.filled_avg_price) if o.filled_avg_price else np.nan
        filled = float(o.filled_qty or 0)
        close = closes[o.symbol].get(session, np.nan) if o.symbol in closes else np.nan
        sign = 1 if side == "buy" else -1
        rows.append({
            "session": session, "symbol": o.symbol, "side": side,
            "qty": float(o.qty or 0), "filled_qty": filled, "fill": fill, "close": close,
            "notional": filled * fill if filled else 0.0,
            "slippage_bps": sign * (fill / close - 1) * 1e4,
            "status": str(o.status),
        })
    ex = pd.DataFrame(rows, columns=["session", "symbol", "side", "qty", "filled_qty", "fill", "close",
                                     "notional", "slippage_bps", "status"])

    return ex

# Execution summary
def risk_fill_summary(ex):
    """
    Order counts, fill rate and notional-weighted slippage.

    Parameters
    ----------
    ex : pd.DataFrame
        Output of risk_fills.

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
    >>> s = risk_fill_summary(risk_fills(orders, closes, "demo"))
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
