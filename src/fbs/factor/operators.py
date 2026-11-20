'''
operators.py - Factor formula operators.
'''

# %%
# Imports
import numba
import numpy as np
import pandas as pd

# %%
# Helpers

# Float array of a wide table
def _array(x):
    return np.asarray(x, dtype=np.float64)

# Float array of window lengths
def _window_array(d, x):
    """
    Window lengths `d` as a float array with the shape of `x`, after checking
    that they line up with `x` and are whole numbers.

    Parameters
    ----------
    d : int or pd.DataFrame
        Window length in bars.
        Index = timestamp, Columns = instrument_id when a DataFrame.
    x : pd.DataFrame
        Wide table. Index = timestamp, Columns = instrument_id.

    Returns
    -------
    windows : np.ndarray
        Window length per cell with the shape of `x`.

    Raises
    ------
    ValueError
        If `d` is a DataFrame with a different index or columns than `x`.
        If `d` has values that are not whole numbers or NaN.
    """

    # If `d` is a DataFrame
    if isinstance(d, pd.DataFrame):
        if not (d.index.equals(x.index) and d.columns.equals(x.columns)):
            raise ValueError("d must have the same index and columns as x")
        values = _array(d)
    # If `d` is a single fixed number for all cells
    else:
        values = np.float64(d)

    # Check that every window is a whole number or NaN
    whole_num = np.isnan(values) | (np.isfinite(values) & (values == np.floor(values)))
    if not np.all(whole_num):
        raise ValueError("d must be whole numbers")

    # Spread the windows to the shape of x, as a view without copying
    return np.broadcast_to(values, x.shape)

# Convert a wide arrary to a wide table
def _wide(values, x):
    return pd.DataFrame(values, index=x.index, columns=x.columns)

# %%
# Kernels

# Delay Kernel: value of x from d bars earlier cell by cell
@numba.njit(parallel=True, cache=True)
def _delay_kernel(x, d):
    m, n = x.shape
    out = np.full((m, n), np.nan)
    for i in numba.prange(n):
        for t in range(m):
            w = d[t, i]
            if np.isnan(w) or w < 0 or t - int(w) < 0:
                continue
            out[t, i] = x[t - int(w), i]
    return out

# Window Kernel: Minimum, mean, bars since the maximum or bars since the minimum of x over the
# past d bars, chosen by stat = 0, 1, 2 or 3, cell by cell
@numba.njit(parallel=True, cache=True)
def _window_kernel(x, d, stat):
    m, n = x.shape
    out = np.full((m, n), np.nan)
    for i in numba.prange(n):
        for t in range(m):
            w = d[t, i]
            if np.isnan(w) or w < 1 or t - int(w) + 1 < 0:
                continue
            first = t - int(w) + 1
            # Scan from the current bar back, so ties keep the most recent bar
            best = x[t, i]
            best_lag = 0
            total = 0.0
            has_nan = False
            for s in range(t, first - 1, -1):
                v = x[s, i]
                if np.isnan(v):
                    has_nan = True
                    break
                total += v
                if (stat == 0 or stat == 3) and v < best:
                    best = v
                    best_lag = t - s
                elif stat == 2 and v > best:
                    best = v
                    best_lag = t - s
            if has_nan:
                continue
            if stat == 0:
                out[t, i] = best
            elif stat == 1:
                out[t, i] = total / int(w)
            else:
                out[t, i] = best_lag
    return out

# Average ranks of the values, with ties sharing their mean rank
@numba.njit(cache=True)
def _ranks(v):
    order = np.argsort(v, kind="mergesort")
    ranks = np.empty(v.size)
    k = 0
    while k < v.size:
        last = k
        while last + 1 < v.size and v[order[last + 1]] == v[order[k]]:
            last += 1
        for q in range(k, last + 1):
            ranks[order[q]] = (k + last) / 2 + 1
        k = last + 1
    return ranks

# Spearman rank correlation of x and y over each window
@numba.njit(parallel=True, cache=True)
def _spearman_kernel(x, y, d):
    m, n = x.shape
    out = np.full((m, n), np.nan)
    for i in numba.prange(n):
        for t in range(m):
            w = d[t, i]
            if np.isnan(w) or w < 1 or t - int(w) + 1 < 0:
                continue
            xs = x[t - int(w) + 1:t + 1, i]
            ys = y[t - int(w) + 1:t + 1, i]
            if np.isnan(xs).any() or np.isnan(ys).any():
                continue
            rx = _ranks(xs) - (int(w) + 1) / 2
            ry = _ranks(ys) - (int(w) + 1) / 2
            sxx = (rx * rx).sum()
            syy = (ry * ry).sum()
            if sxx == 0 or syy == 0:
                continue
            out[t, i] = (rx * ry).sum() / np.sqrt(sxx * syy)
    return out

# %%
# Time-series operators

# Delay
def delay(x, d):
    """
    Value of `x` d bars before the current bar.

    Parameters
    ----------
    x : pd.DataFrame
        Input values. Index = timestamp, Columns = instrument_id.
    d : int or pd.DataFrame
        Number of bars back, 0 for the current bar. Index = timestamp,
        Columns = instrument_id when a DataFrame.

    Returns
    -------
    out : pd.DataFrame
        Delayed values. NaN where d is NaN or negative, or the bar is before
        the first row. Index = timestamp, Columns = instrument_id.

    Raises
    ------
    ValueError
        If d is a DataFrame with a different index or columns than `x`.
        If d has values that are not whole numbers.
    """

    out = _delay_kernel(_array(x), _window_array(d, x))

    return _wide(out, x)

# Window minimum
def ts_min(x, d):
    """
    Minimum of `x` over the past d bars, including the current bar.

    Parameters
    ----------
    x : pd.DataFrame
        Input values. Index = timestamp, Columns = instrument_id.
    d : int or pd.DataFrame
        Window length in bars. Index = timestamp, Columns = instrument_id when a
        DataFrame.

    Returns
    -------
    out : pd.DataFrame
        Window minimum. NaN where d is NaN or below 1, the window has fewer than
        d bars, or the window has a NaN. Index = timestamp,
        Columns = instrument_id.

    Raises
    ------
    ValueError
        If d is a DataFrame with a different index or columns than `x`.
        If d has values that are not whole numbers.
    """

    out = _window_kernel(_array(x), _window_array(d, x), 0)

    return _wide(out, x)

# Window mean
def ts_mean(x, d):
    """
    Mean of `x` over the past d bars, including the current bar.

    Parameters
    ----------
    x : pd.DataFrame
        Input values. Index = timestamp, Columns = instrument_id.
    d : int or pd.DataFrame
        Window length in bars. Index = timestamp, Columns = instrument_id when a
        DataFrame.

    Returns
    -------
    out : pd.DataFrame
        Window mean. NaN where d is NaN or below 1, the window has fewer than d
        bars, or the window has a NaN. Index = timestamp,
        Columns = instrument_id.

    Raises
    ------
    ValueError
        If d is a DataFrame with a different index or columns than `x`.
        If d has values that are not whole numbers.
    """

    out = _window_kernel(_array(x), _window_array(d, x), 1)

    return _wide(out, x)

# Bars since the window maximum
def ts_argmax(x, d):
    """
    Number of bars from the maximum of `x` over the past d bars to the current
    bar, 0 when the maximum is at the current bar. Ties take the most recent bar.

    Parameters
    ----------
    x : pd.DataFrame
        Input values. Index = timestamp, Columns = instrument_id.
    d : int or pd.DataFrame
        Window length in bars. Index = timestamp, Columns = instrument_id when a
        DataFrame.

    Returns
    -------
    out : pd.DataFrame
        Bars since the window maximum. NaN where d is NaN or below 1, the window
        has fewer than d bars, or the window has a NaN. Index = timestamp,
        Columns = instrument_id.

    Raises
    ------
    ValueError
        If d is a DataFrame with a different index or columns than `x`.
        If d has values that are not whole numbers.
    """

    out = _window_kernel(_array(x), _window_array(d, x), 2)

    return _wide(out, x)

# Bars since the window minimum
def ts_argmin(x, d):
    """
    Number of bars from the minimum of `x` over the past d bars to the current
    bar, 0 when the minimum is at the current bar. Ties take the most recent bar.

    Parameters
    ----------
    x : pd.DataFrame
        Input values. Index = timestamp, Columns = instrument_id.
    d : int or pd.DataFrame
        Window length in bars. Index = timestamp, Columns = instrument_id when a
        DataFrame.

    Returns
    -------
    out : pd.DataFrame
        Bars since the window minimum. NaN where d is NaN or below 1, the window
        has fewer than d bars, or the window has a NaN. Index = timestamp,
        Columns = instrument_id.

    Raises
    ------
    ValueError
        If d is a DataFrame with a different index or columns than `x`.
        If d has values that are not whole numbers.
    """

    out = _window_kernel(_array(x), _window_array(d, x), 3)

    return _wide(out, x)

# Window Spearman correlation
def ts_spearman(x, y, d):
    """
    Spearman rank correlation of `x` and `y` over the past d bars, including the
    current bar, with tied values sharing their mean rank.

    Parameters
    ----------
    x : pd.DataFrame
        First input values. Index = timestamp, Columns = instrument_id.
    y : pd.DataFrame
        Second input values. Index = timestamp, Columns = instrument_id.
    d : int or pd.DataFrame
        Window length in bars. Index = timestamp, Columns = instrument_id when a
        DataFrame.

    Returns
    -------
    out : pd.DataFrame
        Window Spearman correlation. NaN where d is NaN or below 1, the window
        has fewer than d bars, the window has a NaN, or `x` or `y` is constant
        in the window. Index = timestamp, Columns = instrument_id.

    Raises
    ------
    ValueError
        If `y` has a different index or columns than `x`.
        If d is a DataFrame with a different index or columns than `x`.
        If d has values that are not whole numbers.
    """

    # Check that y lines up with x
    if not (y.index.equals(x.index) and y.columns.equals(x.columns)):
        raise ValueError("y must have the same index and columns as x")

    out = _spearman_kernel(_array(x), _array(y), _window_array(d, x))

    return _wide(out, x)

# Bar count
def ts_step(c, x):
    """
    Count that grows by c at each bar: c at the first bar, 2c at the second,
    and so on, the same in every column.

    Parameters
    ----------
    c : float
        Step per bar.
    x : pd.DataFrame
        Wide table whose index and columns the result takes. Index = timestamp,
        Columns = instrument_id.

    Returns
    -------
    out : pd.DataFrame
        Bar count times c. Index = timestamp, Columns = instrument_id.
    """

    # Count the rows from the first row, repeated in every column
    counts = np.arange(1, x.shape[0] + 1, dtype=np.float64) * c
    out = pd.DataFrame(np.repeat(counts[:, None], x.shape[1], axis=1),
                       index=x.index, columns=x.columns)

    return out

# %%
# Element-wise operators

# Natural logarithm
def log(x):
    """
    Natural logarithm of `x`.

    Parameters
    ----------
    x : pd.DataFrame
        Input values. Index = timestamp, Columns = instrument_id.

    Returns
    -------
    out : pd.DataFrame
        Natural logarithm. NaN where `x` is 0 or below. Index = timestamp,
        Columns = instrument_id.
    """

    out = np.log(x.where(x > 0))

    return out

# Element-wise maximum
def max(x, y):
    """
    Larger of `x` and `y` in each cell.

    Parameters
    ----------
    x : pd.DataFrame
        First input values. Index = timestamp, Columns = instrument_id.
    y : float or pd.DataFrame
        Second input values. Index = timestamp, Columns = instrument_id when a
        DataFrame.

    Returns
    -------
    out : pd.DataFrame
        Larger value. NaN where `x` or `y` is NaN. Index = timestamp,
        Columns = instrument_id.
    """

    out = np.maximum(x, y)

    return out

# Condition
def where(c, x, y):
    """
    `x` where condition c holds, `y` elsewhere, as in c ? x : y.

    Parameters
    ----------
    c : pd.DataFrame
        Condition per cell. Index = timestamp, Columns = instrument_id.
    x : float or pd.DataFrame
        Values where c holds. Index = timestamp, Columns = instrument_id when a
        DataFrame.
    y : float or pd.DataFrame
        Values where c does not hold. Index = timestamp,
        Columns = instrument_id when a DataFrame.

    Returns
    -------
    out : pd.DataFrame
        Chosen values. Index = timestamp, Columns = instrument_id.
    """

    # Pick from x or y cell by cell
    x = x.to_numpy(dtype=np.float64) if isinstance(x, pd.DataFrame) else x
    y = y.to_numpy(dtype=np.float64) if isinstance(y, pd.DataFrame) else y
    out = pd.DataFrame(np.where(c.to_numpy(dtype=bool), x, y),
                       index=c.index, columns=c.columns)

    return out

# Logical and
def and_(a, b):
    """
    Whether both conditions hold, as in a && b.

    Parameters
    ----------
    a : pd.DataFrame
        First condition per cell. Index = timestamp, Columns = instrument_id.
    b : pd.DataFrame
        Second condition per cell. Index = timestamp, Columns = instrument_id.

    Returns
    -------
    out : pd.DataFrame
        True where both hold. Index = timestamp, Columns = instrument_id.
    """

    out = a & b

    return out
