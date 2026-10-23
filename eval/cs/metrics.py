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
    Cross-sectional Spearman correlation between signal and forward return on each bar.

    Parameters
    ----------
    signal : pd.DataFrame
        Signal values. Index = timestamp, columns = symbol.
    fwd_ret : pd.DataFrame
        Forward returns. Index = timestamp, columns = symbol.

    Returns
    -------
    rankic : pd.Series
        Rank IC per timestamp.
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
    Newey & West (1994) lag selection for the Bartlett kernel.

    Parameters
    ----------
    x : pd.Series
        Time series per timestamp.

    Returns
    -------
    lag : int
        Lag for the Newey-West standard error.
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
        return 0

    # Optimal bandwidth for the estimator of the long-run variance based on the Bartlett kernel
    bandwidth = 1.1447 * abs(s1 / s0) ** (2 / 3) * T ** (1 / 3)
    return int(min(bandwidth, T - 1))


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
    result : dict (cheaper than pd.DataFrame)
        Test summary.
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
    Bucket forward returns by signal quantiles.

    Parameters
    ----------
    signal : pd.DataFrame
        Signal values. Index = timestamp, columns = symbol.
    fwd_ret : pd.DataFrame
        Forward returns. Index = timestamp, columns = symbol.
    n_quantiles : int
        Number of quantiles.
    winsor : float
        Winsorization level for forward returns.

    Returns
    -------
    buckets : pd.DataFrame
        Bucketed forward returns. Index = timestamp, columns = bucket number.
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
    Long-short quantile spread, half capital long the top bucket, half short the
    bottom bucket.

    Parameters
    ----------
    buckets : pd.DataFrame
        Bucketed forward returns. Index = timestamp, columns = bucket number.

    Returns
    -------
    spread : pd.Series
        Quantile spread per timestamp.
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
        columns = bucket number.

    Returns
    -------
    u_shape_flag : bool
        True if the factor is U-shaped or inverted U-shaped.
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
        Signal values. Index = timestamp, columns = symbol.
    fwd_rets : pd.DataFrame
        Forward returns r(k) for k = 0..H, from the close of bar t+k to the
        close of bar t+k+1. Index = timestamp, columns = (k, symbol).

    Returns
    -------
    decay : pd.Series
        Mean Rank IC per k.
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
    Fit IC(k) = IC(0) * exp(-lambda * k) to the mean Rank IC and return the
    decay rate and half-life.

    Parameters
    ----------
    decay : pd.Series
        Mean Rank IC per k.

    Returns
    -------
    result : dict
        lambda, half_life (np.inf if lambda <= 0).
    """

    # IC(0) is the mean Rank IC at k = 0
    ic0 = decay.loc[0]

    # Decay model
    def model(x, lam):
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
    Percentage of symbols in the top and bottom buckets that were not in the same
    bucket on the previous bar.

    Parameters
    ----------
    signal : pd.DataFrame
        Signal values. Index = timestamp, columns = symbol.
    n_quantiles : int
        Number of quantiles.

    Returns
    -------
    turnover : pd.DataFrame
        Turnover of the top and bottom buckets. Index = timestamp,
        columns = top, bottom.
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
        columns = top, bottom.

    Returns
    -------
    summary : pd.DataFrame
        Summary statistics.
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
def quantile_equity(spread, capital=1.0):
    """
    Equity of the long-short portfolio, compounding the quantile spread
    from an initial capital.

    Parameters
    ----------
    spread : pd.Series
        Quantile spread per timestamp (without winsorization).
    capital : float
        Initial capital.

    Returns
    -------
    equity : pd.Series
        Equity per timestamp.
    """

    # Record the return on bar t+1
    realized = spread.shift(1, fill_value=0)

    # Compounded equity, starting from the capital on the first bar
    equity = capital * (1 + realized).cumprod()

    return equity

# %%
# Quantile Sharpe

# Quantile Sharpe ratio
def quantile_sharpe(spread, bars_per_year):
    """
    Annualized Sharpe ratio of the long-short equity curve.

    Parameters
    ----------
    spread : pd.Series
        Quantile spread per timestamp (without winsorization).
    bars_per_year : float
        Number of bars per year.

    Returns
    -------
    sharpe : float
        Annualized Sharpe ratio.
    """

    # Returns of the equity curve
    equity = quantile_equity(spread)
    ret = equity.pct_change().dropna()

    # Annualized Sharpe ratio
    sharpe = ret.mean() / ret.std() * np.sqrt(bars_per_year)

    return sharpe

# %%
# Quantile Max Drawdown

# Quantile maximum drawdown
def quantile_max_drawdown(spread):
    """
    Maximum drawdown of the long-short equity curve.

    Parameters
    ----------
    spread : pd.Series
        Quantile spread per timestamp (without winsorization).

    Returns
    -------
    max_drawdown : float
        Largest peak-to-trough loss as a percentage of the peak.
    """

    # Equity curve, initial capital does not matter for drawdown
    equity = quantile_equity(spread)

    # Running peak
    peak = equity.cummax()

    # Drawdown per timestamp and its minimum
    drawdown = equity / peak - 1
    max_drawdown = drawdown.min() * 100

    return max_drawdown

# %%
# Risk Profile

# Factor risk profile
def risk_profile(spread, risk_factors, freq):
    """
    Regress the long-short spread on common risk factors.

    Parameters
    ----------
    spread : pd.Series
        Quantile spread per timestamp (without winsorization).
    risk_factors : pd.DataFrame
        Risk factor returns. Index = period label at freq, columns = risk factor.
    freq : str
        pandas frequency of the risk factors.

    Returns
    -------
    result : dict
        coef, se, t : pd.Series per alpha and risk factor;
        r2_adj : float, adjusted R-squared.
    """

    # Returns of the equity curve
    equity = quantile_equity(spread)
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