'''
weight_limits.py - risk_weights: target weights within config.yaml
paper.limits (gross, net, single-name weight, shorts).
'''

# %%
# Imports

import numpy as np

# %%
# Constants

# Tolerance for float sums compared with config.yaml paper.limits
TOL = 1e-9

# %%
# Checks

# Weights check
def risk_weights(weights, limits):
    """
    Check the signal session's target weights against the config.yaml paper.limits.

    Parameters
    ----------
    weights : pd.Series
        Target weight per symbol.
    limits : dict
        config.yaml paper.limits: max_gross, max_net, max_weight, allow_shorts.

    Returns
    -------
    failures : list of str
        Empty if all limits hold.
    """

    w = weights.dropna().astype(float)

    # Infinite weights make every other check meaningless
    if not np.isfinite(w).all():
        return ["weights contain inf"]

    # Gross, net and single-name exposure
    failures = []
    if w.abs().sum() > limits["max_gross"] + TOL:
        failures.append(f"gross {w.abs().sum():.3f} > max_gross {limits['max_gross']}")
    if abs(w.sum()) > limits["max_net"] + TOL:
        failures.append(f"net {w.sum():.3f} > max_net {limits['max_net']}")
    if len(w) and w.abs().max() > limits["max_weight"] + TOL:
        failures.append(f"max weight {w.abs().max():.3f} > max_weight {limits['max_weight']}")

    # Shorts only when allowed
    if not limits["allow_shorts"] and (w < 0).any():
        failures.append("negative weights but allow_shorts is false")

    return failures
