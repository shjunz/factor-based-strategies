'''
metrics.py

'''

# %%
# Imports

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.tsa.stattools import acovf
from scipy.optimize import curve_fit

# %%
# Rank IC

# Rank IC calculation
def rank_ic(signal, fwd_ret):
    """
    Spearman correlation between signal and forward return.

    Parameters
    ----------
    signal : pd.DataFrame
        Signal values. Index = timestamp, Columns = symbol.
    fwd_ret : pd.DataFrame
        Forward returns. Index = timestamp, Columns = symbol.

    Returns
    -------
    rankic : pd.Series
        Rank IC per timestamp.

    Examples
    --------
    >>> idx = pd.date_range("2024-01-01", periods=3)
    >>> signal = pd.DataFrame([[1, 2, 3, 4, 5], [5, 4, 3, 2, 1], [1, 3, 2, 5, 4]],
    ...                       index=idx, columns=list("ABCDE"), dtype=float)
    >>> fwd_ret = pd.DataFrame([[.01, .02, .03, .04, .05],
    ...                         [.01, .02, .03, .04, .05],
    ...                         [.02, .01, .03, .05, .04]],
    ...                        index=idx, columns=list("ABCDE"))
    >>> rank_ic(signal, fwd_ret)
    2024-01-01    1.0
    2024-01-02   -1.0
    2024-01-03    0.7
    Freq: D, dtype: float64
    """

    # Align signal and forward return
    s, r = signal.align(fwd_ret, join="inner")

    # Drop NaN values
    valid = s.notna() & r.notna()
    s, r = s.where(valid), r.where(valid)

    # Calculate rank IC per timestamp
    rankic = s.rank(axis=1).corrwith(r.rank(axis=1), axis=1)

    return rankic.dropna()


# Newey & West lag selection
def nw_lag(x):
    """
    Newey & West lag selection for the Bartlett kernel.

    Parameters
    ----------
    x : pd.Series
        Time series per timestamp.

    Returns
    -------
    lag : int
        Lag for the Newey-West standard error.

    Examples
    --------
    >>> ic = pd.Series(np.random.default_rng(0).normal(0.05, 0.1, 250))
    >>> nw_lag(ic)
    4
    >>> nw_lag(np.ones(10))
    2
    """
    x = np.asarray(x, dtype=float)
    T = len(x)

    # Pilot lag n = floor(4 * (T / 100) ^ (2/9))
    # Calculate autocovariance function up to lag n
    n = int(4 * (T / 100) ** (2 / 9))
    gamma = acovf(x, adjusted=False, nlag=n, fft=True)

    # s0: long-run variance
    # s1: lag-weighted autocovariance
    s0 = gamma[0] + 2 * gamma[1:].sum()
    s1 = 2 * (np.arange(1, n + 1) * gamma[1:]).sum()
    if s0 <= 0 or s1 == 0:
        return n

    # Optimal bandwidth for the estimator of the long-run variance based on the Bartlett kernel
    bandwidth = 1.1447 * abs(s1 / s0) ** (2 / 3) * T ** (1 / 3)

    # Pilot lag as the lower bound
    return int(min(max(bandwidth, n), T - 1))


# Newey-West t-test
def nw_test(x):
    """
    One-sample t-test with Newey-West standard error.

    Parameters
    ----------
    x : pd.Series
        Time series per timestamp.

    Returns
    -------
    result : dict
        Test summary.

    Examples
    --------
    >>> ic = pd.Series(np.random.default_rng(0).normal(0.05, 0.1, 250))
    >>> result = nw_test(ic)
    >>> {k: round(float(v), 4) for k, v in result.items()}
    {'mean': 0.0494, 'lag': 4.0, 'se': 0.0068, 't': 7.2388, 'p': 0.0, 'ci_low': 0.036, 'ci_high': 0.0628}
    """
    x = np.asarray(x, dtype=float)
    lag = nw_lag(x)

    # One-sample t-test with Newey-West standard error
    result = sm.OLS(x, np.ones(len(x))).fit(
        cov_type="HAC", cov_kwds={"maxlags": lag, "use_correction": False}
    )
    ci_low, ci_high = result.conf_int()[0]

    return {
        "mean": result.params[0],
        "lag": lag,
        "se": result.bse[0],
        "t": result.tvalues[0],
        "p": result.pvalues[0],
        "ci_low": ci_low,
        "ci_high": ci_high,
    }


# Summary statistics for Rank IC
def summary_rankic(ic):
    """
    Summary statistics for Rank IC.

    Parameters
    ----------
    ic : pd.Series
        Rank IC per timestamp.

    Returns
    -------
    summary : pd.DataFrame
        Summary statistics.

    Examples
    --------
    >>> ic = pd.Series(np.random.default_rng(0).normal(0.05, 0.1, 250))
    >>> summary_rankic(ic)[["mean", "lag", "t", "ir", "win_rate"]].round(3)
        mean  lag      t     ir  win_rate
    0  0.049    4  7.239  0.485      0.68
    """
    result = nw_test(ic)
    summary = pd.DataFrame(
        {
            "mean": [result["mean"]],
            "lag": [result["lag"]],
            "se": [result["se"]],
            "t": [result["t"]],
            "p": [result["p"]],
            "ci_low": [result["ci_low"]],
            "ci_high": [result["ci_high"]],
            "ir": [ic.mean() / ic.std()],
            "win_rate": [(ic > 0).mean()],
            "skew": [ic.skew()],
            "kurt": [ic.kurt() + 3],
        }
    )
    return summary

# %%
# Quantile Spread

# Bucket returns
def bucket_returns(signal, fwd_ret, n_quantiles=5, winsor=0.0):
    """
    Mean forward returns of signal quantile buckets.

    Parameters
    ----------
    signal : pd.DataFrame
        Signal values. Index = timestamp, Columns = symbol.
    fwd_ret : pd.DataFrame
        Forward returns. Index = timestamp, Columns = symbol.
    n_quantiles : int
        Number of quantiles.
    winsor : float
        Winsorization level for forward returns.

    Returns
    -------
    buckets : pd.DataFrame
        Bucketed forward returns. Index = timestamp, Columns = bucket number.

    Examples
    --------
    >>> idx = pd.date_range("2024-01-01", periods=3)
    >>> signal = pd.DataFrame([[1, 2, 3, 4, 5], [5, 4, 3, 2, 1], [1, 3, 2, 5, 4]],
    ...                       index=idx, columns=list("ABCDE"), dtype=float)
    >>> fwd_ret = pd.DataFrame([[.01, .02, .03, .04, .05],
    ...                         [.01, .02, .03, .04, .05],
    ...                         [.02, .01, .03, .05, .04]],
    ...                        index=idx, columns=list("ABCDE"))
    >>> bucket_returns(signal, fwd_ret, n_quantiles=5)
                   1     2     3     4     5
    2024-01-01  0.01  0.02  0.03  0.04  0.05
    2024-01-02  0.05  0.04  0.03  0.02  0.01
    2024-01-03  0.02  0.03  0.01  0.04  0.05
    >>> bucket_returns(signal, fwd_ret, n_quantiles=2)
                    1         2
    2024-01-01  0.015  0.040000
    2024-01-02  0.045  0.020000
    2024-01-03  0.025  0.033333
    """

    # Align signal and forward return
    s, r = signal.align(fwd_ret, join="inner")

    # Drop NaN values
    valid = s.notna() & r.notna()
    s, r = s.where(valid), r.where(valid)

    # Assign buckets by cross-sectional percentile rank: (0, 1] -> 1..K
    # bucket 1 = lowest signal, bucket K = highest signal
    bucket = np.ceil(s.rank(axis=1, pct=True) * n_quantiles)

    # Winsorize forward returns per timestamp
    if winsor > 0:
        lower = r.quantile(winsor, axis=1)
        upper = r.quantile(1 - winsor, axis=1)
        r = r.clip(lower=lower, upper=upper, axis=0)

    # Mean forward return of each bucket per timestamp
    buckets = {}
    for k in range(1, n_quantiles + 1):
        r_k = r.where(bucket == k)
        buckets[k] = r_k.mean(axis=1)
    buckets = pd.DataFrame(buckets)

    return buckets


# Quantile spread calculation
def quantile_spread(buckets):
    """
    Long-short quantile spread.

    Parameters
    ----------
    buckets : pd.DataFrame
        Bucketed forward returns. Index = timestamp, Columns = bucket number.

    Returns
    -------
    spread : pd.Series
        Quantile spread per timestamp.

    Examples
    --------
    >>> idx = pd.date_range("2024-01-01", periods=3)
    >>> signal = pd.DataFrame([[1, 2, 3, 4, 5], [5, 4, 3, 2, 1], [1, 3, 2, 5, 4]],
    ...                       index=idx, columns=list("ABCDE"), dtype=float)
    >>> fwd_ret = pd.DataFrame([[.01, .02, .03, .04, .05],
    ...                         [.01, .02, .03, .04, .05],
    ...                         [.02, .01, .03, .05, .04]],
    ...                        index=idx, columns=list("ABCDE"))
    >>> quantile_spread(bucket_returns(signal, fwd_ret, n_quantiles=5))
    2024-01-01    0.020
    2024-01-02   -0.020
    2024-01-03    0.015
    Freq: D, dtype: float64
    """

    # Long-short
    top, bottom = buckets.columns.max(), buckets.columns.min()
    spread = (buckets[top] - buckets[bottom]) / 2

    return spread.dropna()


# Summary statistics for quantile spread
def summary_spread(spread):
    """
    Summary statistics for quantile spread.

    Parameters
    ----------
    spread : pd.Series
        Quantile spread per timestamp (with winsorization).

    Returns
    -------
    summary : pd.DataFrame
        Summary statistics.

    Examples
    --------
    >>> spread = pd.Series(np.random.default_rng(1).normal(0.002, 0.01, 250))
    >>> summary_spread(spread).round(3)
        mean  lag      t
    0  0.001    4  2.188
    """
    result = nw_test(spread)
    summary = pd.DataFrame(
        {
            "mean": [result["mean"]],
            "lag": [result["lag"]],
            "t": [result["t"]],
        }
    )
    return summary

# %%
# Fama-MacBeth

# Fama-MacBeth factor return
def fama_macbeth(signal, fwd_ret):
    """
    Fama & MacBeth (1973) factor return of the z-scored signal.

    Parameters
    ----------
    signal : pd.DataFrame
        Signal values. Index = timestamp, Columns = symbol.
    fwd_ret : pd.DataFrame
        Forward returns. Index = timestamp, Columns = symbol.

    Returns
    -------
    factor_ret : pd.Series
        Factor return per timestamp.

    Examples
    --------
    >>> idx = pd.date_range("2024-01-01", periods=3)
    >>> signal = pd.DataFrame([[1, 2, 3, 4, 5], [5, 4, 3, 2, 1], [1, 3, 2, 5, 4]],
    ...                       index=idx, columns=list("ABCDE"), dtype=float)
    >>> fwd_ret = pd.DataFrame([[.01, .02, .03, .04, .05],
    ...                         [.01, .02, .03, .04, .05],
    ...                         [.02, .01, .03, .05, .04]],
    ...                        index=idx, columns=list("ABCDE"))
    >>> fama_macbeth(signal, fwd_ret).round(4)
    2024-01-01    0.0158
    2024-01-02   -0.0158
    2024-01-03    0.0111
    Freq: D, dtype: float64
    """

    # Align signal and forward return
    s, r = signal.align(fwd_ret, join="inner")

    # Drop NaN values
    valid = s.notna() & r.notna()
    s, r = s.where(valid), r.where(valid)

    # z-score signal per timestamp
    z = s.sub(s.mean(axis=1), axis=0).div(s.std(axis=1), axis=0)

    # OLS slope with intercept per timestamp: sum(z * (r - mean(r))) / sum(z^2)
    r_dm = r.sub(r.mean(axis=1), axis=0)
    factor_ret = (z * r_dm).sum(axis=1) / (z ** 2).sum(axis=1)

    return factor_ret.dropna()


# Summary statistics for Fama-MacBeth factor return
def summary_fama_macbeth(factor_ret):
    """
    Summary statistics for Fama-MacBeth factor return.

    Parameters
    ----------
    factor_ret : pd.Series
        Factor return per timestamp.

    Returns
    -------
    summary : pd.DataFrame
        Summary statistics.

    Examples
    --------
    >>> factor_ret = pd.Series(np.random.default_rng(1).normal(0.002, 0.01, 250))
    >>> summary_fama_macbeth(factor_ret).round(3)
        mean  lag      t
    0  0.001    4  2.188
    """
    result = nw_test(factor_ret)
    summary = pd.DataFrame(
        {
            "mean": [result["mean"]],
            "lag": [result["lag"]],
            "t": [result["t"]],
        }
    )
    return summary

# %%
# Direction Check

# Reverse Check
def reverse_check(ic, spread):
    """
    Check if the factor is negatively related to forward returns.

    Parameters
    ----------
    ic : pd.Series
        Rank IC per timestamp.
    spread : pd.Series
        Quantile spread per timestamp (with winsorization).

    Returns
    -------
    reverse_flag : bool
        True if both the mean Rank IC and the mean quantile spread are negative.

    Examples
    --------
    >>> reverse_check(pd.Series([-0.02, -0.01]), pd.Series([-0.001, 0.0]))
    True
    >>> reverse_check(pd.Series([0.02, 0.01]), pd.Series([-0.001, 0.0]))
    False
    """

    # Both mean Rank IC and mean quantile spread are negative
    reverse_flag = bool(ic.mean() < 0 and spread.mean() < 0)
    return reverse_flag


# U-shape Check
def u_shape_check(buckets):
    """
    Check if both end buckets beat or trail the middle buckets.

    Parameters
    ----------
    buckets : pd.DataFrame
        Bucketed forward returns (with winsorization). Index = timestamp,
        Columns = bucket number.

    Returns
    -------
    u_shape_flag : bool
        True if the factor is U-shaped or inverted U-shaped.

    Examples
    --------
    >>> u_shape_check(pd.DataFrame({1: [0.03], 2: [0.0], 3: [0.01], 4: [0.02]}))
    True
    >>> u_shape_check(pd.DataFrame({1: [0.0], 2: [0.01], 3: [0.02], 4: [0.03]}))
    False
    """

    # Mean forward return of each bucket over time
    means = buckets.mean()

    # End buckets
    bottom, top = means.index.min(), means.index.max()
    # Middle buckets
    middle = means.drop([bottom, top]).mean()

    # U shape: both ends above the middle
    # Inverted U shape: both ends below the middle
    u_shape = means[bottom] > middle and means[top] > middle
    inverted_u = means[bottom] < middle and means[top] < middle

    u_shape_flag = bool(u_shape or inverted_u)

    return u_shape_flag

# %%
# IC Decay

# Mean Rank IC decay calculation
def ic_decay(signal, fwd_rets):
    """
    Mean Rank IC between signal and forward returns k bars later.

    Parameters
    ----------
    signal : pd.DataFrame
        Signal values. Index = timestamp, Columns = symbol.
    fwd_rets : pd.DataFrame
        Forward returns r(k) for k = 0..H, from the close of bar t+k to the
        close of bar t+k+1. Index = timestamp, Columns = (k, symbol).

    Returns
    -------
    decay : pd.Series
        Mean Rank IC per k.

    Examples
    --------
    >>> idx = pd.date_range("2024-01-01", periods=3)
    >>> signal = pd.DataFrame([[1, 2, 3, 4, 5], [5, 4, 3, 2, 1], [1, 3, 2, 5, 4]],
    ...                       index=idx, columns=list("ABCDE"), dtype=float)
    >>> fwd_ret = pd.DataFrame([[.01, .02, .03, .04, .05],
    ...                         [.01, .02, .03, .04, .05],
    ...                         [.02, .01, .03, .05, .04]],
    ...                        index=idx, columns=list("ABCDE"))
    >>> fwd_rets = pd.concat({0: fwd_ret, 1: fwd_ret.shift(-1)}, axis=1)
    >>> ic_decay(signal, fwd_rets)
    0    0.233333
    1    0.100000
    dtype: float64
    """

    # Mean Rank IC for each k
    decay = {}
    # level=0 is k, level=1 is symbol
    for k in fwd_rets.columns.unique(level=0):
        decay[k] = rank_ic(signal, fwd_rets[k]).mean()
    decay = pd.Series(decay).sort_index()

    return decay


# IC Half-life
def ic_half_life(decay):
    """
    Half-life of the mean Rank IC decay.

    Parameters
    ----------
    decay : pd.Series
        Mean Rank IC per k.

    Returns
    -------
    result : dict
        lambda, half_life (np.inf if lambda <= 0).

    Examples
    --------
    >>> result = ic_half_life(pd.Series([0.08, 0.04, 0.02, 0.01]))
    >>> {k: round(float(v), 4) for k, v in result.items()}
    {'lambda': 0.6931, 'half_life': 1.0}
    >>> ic_half_life(pd.Series([0.05, 0.05, 0.06]))["half_life"]
    inf
    """

    # IC(0) is the mean Rank IC at k = 0
    ic0 = decay.loc[0]

    # Decay model
    def model(x, lam):
        """
        Exponential decay IC(k) = IC(0) * exp(-lam * k), with IC(0) fixed to
        the observed mean Rank IC at k = 0.

        Parameters
        ----------
        x : np.ndarray
            Lags k.
        lam : float
            Decay rate per bar.

        Returns
        -------
        ic : np.ndarray
            Modelled mean Rank IC per k.

        Examples
        --------
        With ic0 = 0.08:

        >>> model(np.array([0.0, 1.0]), np.log(2))  # doctest: +SKIP
        array([0.08, 0.04])
        """
        return ic0 * np.exp(-lam * x)
    
    # Nonlinear least squares fit of lambda
    k = decay.index.to_numpy(dtype=float)
    popt, _ = curve_fit(model, k, decay.to_numpy(), p0=[0.1])
    lam = popt[0]

    # Half-life in bars
    if lam > 0:
        half_life = np.log(2) / lam
    else:
        half_life = np.inf

    return {"lambda": lam, "half_life": half_life}

# %%
# Quantile CVaR

# Quantile CVaR calculation
def quantile_cvar(spread, worst=0.05):
    """
    Conditional Value at Risk (CVaR) of the quantile spread.

    Parameters
    ----------
    spread : pd.Series
        Quantile spread per timestamp (without winsorization).
    worst : float
        Percentage of the worst bars to average.

    Returns
    -------
    cvar : float
        Mean long-short spread over the worst bars.

    Examples
    --------
    >>> spread = pd.Series([0.01, -0.03, 0.02, -0.01, 0.0])
    >>> float(quantile_cvar(spread, worst=0.4))
    -0.02
    >>> float(quantile_cvar(spread))
    -0.03
    """

    # Number of worst bars
    n = max(1, int(np.ceil(worst * len(spread))))

    # Mean of the n lowest spreads
    cvar = spread.nsmallest(n).mean()

    return cvar

# %%
# Quantile Turnover

# Quantile turnover calculation
def quantile_turnover(signal, n_quantiles=5):
    """
    Percentage of symbols in the top and bottom buckets that changed in the same
    bucket on the previous bar.

    Parameters
    ----------
    signal : pd.DataFrame
        Signal values. Index = timestamp, Columns = symbol.
    n_quantiles : int
        Number of quantiles.

    Returns
    -------
    turnover : pd.DataFrame
        Turnover of the top and bottom buckets. Index = timestamp,
        Columns = top, bottom.

    Examples
    --------
    >>> signal = pd.DataFrame([[1, 2, 3, 4, 5], [1, 2, 3, 5, 4], [1, 2, 3, 5, 4]],
    ...                       index=pd.date_range("2024-01-01", periods=3),
    ...                       columns=list("ABCDE"), dtype=float)
    >>> quantile_turnover(signal, n_quantiles=5)
                top  bottom
    2024-01-02  1.0     0.0
    2024-01-03  0.0     0.0
    """

    # Assign buckets by cross-sectional percentile rank
    bucket = np.ceil(signal.rank(axis=1, pct=True) * n_quantiles)

    # Top bucket
    now = bucket == n_quantiles
    before = now.shift(1, fill_value=False)
    top = (now & ~before).sum(axis=1) / now.sum(axis=1)

    # Bottom bucket
    now = bucket == 1
    before = now.shift(1, fill_value=False)
    bottom = (now & ~before).sum(axis=1) / now.sum(axis=1)

    # The first bar has no previous bar, drop it
    turnover = pd.DataFrame({"top": top, "bottom": bottom}).iloc[1:]

    return turnover.dropna()


# Summary statistics for quantile turnover
def summary_turnover(turnover):
    """
    Summary statistics for quantile turnover.

    Parameters
    ----------
    turnover : pd.DataFrame
        Turnover of the top and bottom buckets. Index = timestamp,
        Columns = top, bottom.

    Returns
    -------
    summary : pd.DataFrame
        Summary statistics.

    Examples
    --------
    >>> turnover = pd.DataFrame({"top": [1.0, 0.0], "bottom": [0.0, 0.0]})
    >>> summary_turnover(turnover)
       top  bottom  mean
    0  0.5     0.0  0.25
    """
    top, bottom = turnover["top"].mean(), turnover["bottom"].mean()
    summary = pd.DataFrame(
        {
            "top": [top],
            "bottom": [bottom],
            "mean": [(top + bottom) / 2],
        }
    )
    return summary

# %%
# Quantile Equity

# Quantile equity calculation
def quantile_equity(spread, index, capital=1.0):
    """
    Equity of the long-short portfolio.

    Parameters
    ----------
    spread : pd.Series
        Quantile spread per timestamp (without winsorization).
    index : pd.Index
        Timestamp of every bar at the base frequency.
    capital : float
        Initial capital.

    Returns
    -------
    equity : pd.Series
        Equity per base bar.

    Examples
    --------
    >>> bars = pd.date_range("2024-01-01", periods=4)
    >>> spread = pd.Series([0.1, -0.05], index=bars[[0, 2]])
    >>> quantile_equity(spread, bars)
    2024-01-01    1.000
    2024-01-02    1.100
    2024-01-03    1.100
    2024-01-04    1.045
    Freq: D, dtype: float64
    >>> quantile_equity(spread, bars, capital=100).iloc[-1]
    np.float64(104.5)
    """

    # Next base bar of each base bar
    next_bar = pd.Series(index[1:], index=index[:-1])

    # Record the return on bar t+1, zero on bars without a closing position
    realized = pd.Series(spread.to_numpy(), index=spread.index.map(next_bar))
    realized = realized[realized.index.notna()].reindex(index, fill_value=0)

    # Compounded equity, starting from the capital on the first bar
    equity = capital * (1 + realized).cumprod()

    return equity

# %%
# Quantile Sharpe

# Quantile Sharpe ratio
def quantile_sharpe(spread, index, bars_per_year):
    """
    Annualized Sharpe ratio of the long-short equity curve.

    Parameters
    ----------
    spread : pd.Series
        Quantile spread per timestamp (without winsorization).
    index : pd.Index
        Timestamp of every bar at the base frequency.
    bars_per_year : float
        Number of bars per year.

    Returns
    -------
    sharpe : float
        Annualized Sharpe ratio.

    Examples
    --------
    >>> bars = pd.date_range("2024-01-01", periods=6)
    >>> spread = pd.Series([0.01, -0.005, 0.02, 0.0, 0.01], index=bars[:5])
    >>> round(float(quantile_sharpe(spread, bars, bars_per_year=252)), 4)
    11.4008
    """

    # Returns of the equity curve
    equity = quantile_equity(spread, index)
    ret = equity.pct_change().dropna()

    # Annualized Sharpe ratio
    sharpe = ret.mean() / ret.std() * np.sqrt(bars_per_year)

    return sharpe

# %%
# Quantile Max Drawdown

# Quantile maximum drawdown
def quantile_max_drawdown(spread, index):
    """
    Maximum drawdown of the long-short equity curve.

    Parameters
    ----------
    spread : pd.Series
        Quantile spread per timestamp (without winsorization).
    index : pd.Index
        Timestamp of every bar at the base frequency.

    Returns
    -------
    max_drawdown : float
        Largest peak-to-trough loss as a percentage of the peak.

    Examples
    --------
    >>> bars = pd.date_range("2024-01-01", periods=4)
    >>> spread = pd.Series([0.1, -0.05], index=bars[[0, 2]])
    >>> round(float(quantile_max_drawdown(spread, bars)), 4)
    -5.0
    """

    # Equity curve, initial capital does not matter for drawdown
    equity = quantile_equity(spread, index)

    # Running peak
    peak = equity.cummax()

    # Drawdown per timestamp and its minimum
    drawdown = equity / peak - 1
    max_drawdown = drawdown.min() * 100

    return max_drawdown

# %%
# Risk Profile

# Factor risk profile
def risk_profile(spread, index, risk_factors, freq):
    """
    Regression of the long-short spread on common risk factors.

    Parameters
    ----------
    spread : pd.Series
        Quantile spread per timestamp (without winsorization).
    index : pd.Index
        Timestamp of every bar at the base frequency.
    risk_factors : pd.DataFrame
        Risk factor returns. Index = period label at freq, Columns = risk factor.
    freq : str
        pandas frequency of the risk factors.

    Returns
    -------
    result : dict
        coef, se, t : pd.Series per alpha and risk factor;
        r2_adj : float, adjusted R-squared.

    Examples
    --------
    >>> rng = np.random.default_rng(0)
    >>> bars = pd.bdate_range("2020-01-01", "2023-12-29")
    >>> spread = pd.Series(rng.normal(0.0005, 0.01, len(bars)), index=bars)
    >>> monthly = (1 + spread).resample("ME").prod() - 1
    >>> risk_factors = pd.DataFrame(
    ...     {"MKT": monthly.values * 0.5 + rng.normal(0, 0.01, len(monthly)),
    ...      "SMB": rng.normal(0, 0.02, len(monthly))}, index=monthly.index)
    >>> result = risk_profile(spread, bars, risk_factors, "ME")
    >>> result["coef"].round(3)
    alpha    0.002
    MKT      1.442
    SMB     -0.042
    dtype: float64
    >>> round(float(result["r2_adj"]), 3)
    0.51
    """

    # Returns of the equity curve
    equity = quantile_equity(spread, index)
    ret = equity.pct_change().dropna()

    # Compound the returns to the risk factor frequency
    c_ret = (1 + ret).resample(freq).prod(min_count=1) - 1

    # Keep data covered by both the spread and the risk factors
    data = risk_factors.join(c_ret.rename("spread"), how="inner").dropna()

    # Regress the spread on the risk factors with an intercept (alpha)
    y = data["spread"]
    X = sm.add_constant(data.drop(columns="spread")).rename(columns={"const": "alpha"})

    # OLS with Newey-West standard errors
    lag = nw_lag(y)
    result = sm.OLS(y, X).fit(
        cov_type="HAC", cov_kwds={"maxlags": lag, "use_correction": False}
    )

    return {
        "coef": result.params,
        "se": result.bse,
        "t": result.tvalues,
        "r2_adj": result.rsquared_adj,
    }