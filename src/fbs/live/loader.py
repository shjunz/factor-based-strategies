'''
loader.py - Load a strategy folder: config.yaml (research settings plus the
paper block), data.py and weights.py.
'''

# %%
# Imports

import datetime as dt
import importlib.util
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

import yaml

from fbs.live.brokers import BROKERS

# %%
# Constants

# Strategy folders live at <repo>/strategy/<name> (loader.py is at src/fbs/live/)
REPO_ROOT = Path(__file__).resolve().parents[3]
STRATEGY_ROOT = REPO_ROOT / "strategy"

# Required keys of config.yaml, its paper block and paper.limits
REQUIRED_CONFIG = ("universe", "rebalance", "lookback_sessions", "params", "paper")
REQUIRED_PAPER = ("enabled", "account", "capital", "limits")
REQUIRED_LIMITS = ("max_gross", "max_net", "max_weight", "max_turnover",
                   "max_order_notional", "max_orders", "min_order_notional", "allow_shorts")

# Rebalance rules: every session, last session of the week, last session of the month
REBALANCE_RULES = ("D", "W", "M")

# Required keys of config.yaml split (optional block)
REQUIRED_SPLIT = ("is_end", "embargo_sessions")

# Shortest embargo per rebalance rule: one holding period in sessions, so the
# last IS position's return never reaches into OOS
MIN_EMBARGO = {"D": 1, "W": 5, "M": 21}

# %%
# Strategy

# One loaded strategy folder
@dataclass(frozen=True)
class Strategy:
    """
    One loaded strategy folder.

    Attributes
    ----------
    name : str
        Folder name under strategy/.
    folder : Path
        Strategy folder.
    config : dict
        config.yaml.
    paper : dict
        config.yaml paper block (broker, account, capital, limits, enabled).
    data : module
        data.py, defines fetch(config, start, end).
    weights : module
        weights.py, defines compute(data, params).
    """

    name: str
    folder: Path
    config: dict
    paper: dict
    data: ModuleType
    weights: ModuleType

# %%
# Helpers

# Import a .py file as a module
def _import(path, module_name):
    """
    Import a .py file that is not on the Python path.

    Parameters
    ----------
    path : Path
        The .py file.
    module_name : str
        Name to give the module, unique per strategy.

    Returns
    -------
    module : module
        The imported module.

    Raises
    ------
    ImportError
        If `path` cannot be loaded as a module.

    Examples
    --------
    >>> module = _import(STRATEGY_ROOT / "strategy_example" / "weights.py",
    ...                  "fbs_strategy_strategy_example_weights")
    >>> callable(module.compute)
    True
    """

    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    return module

# Read a yaml file
def _read_yaml(path):
    """
    Read a yaml file.

    Parameters
    ----------
    path : Path
        The yaml file.

    Returns
    -------
    content : dict
        Parsed content, {} for an empty file.

    Raises
    ------
    FileNotFoundError
        If `path` does not exist.

    Examples
    --------
    >>> config = _read_yaml(STRATEGY_ROOT / "strategy_example" / "config.yaml")
    >>> config["rebalance"]
    'M'
    """

    if not path.exists():
        raise FileNotFoundError(f"missing {path.relative_to(REPO_ROOT)}")
    with path.open() as f:
        content = yaml.safe_load(f) or {}

    return content

# Required keys check
def _require(mapping, keys, where):
    """
    Raise if any required key is missing.

    Parameters
    ----------
    mapping : dict
        Parsed yaml section.
    keys : tuple of str
        Required keys.
    where : str
        Section name for the error message.

    Returns
    -------
    None

    Raises
    ------
    ValueError
        If a key in `keys` is not in `mapping`.

    Examples
    --------
    >>> _require({"universe": [], "rebalance": "M"}, ("universe", "rebalance"), "config.yaml")
    >>> _require({"universe": []}, ("universe", "rebalance", "paper"), "config.yaml")
    Traceback (most recent call last):
    ...
    ValueError: config.yaml is missing keys: rebalance, paper
    """

    missing = [k for k in keys if k not in mapping]
    if missing:
        raise ValueError(f"{where} is missing keys: {', '.join(missing)}")

# Sample split check
def _check_split(config):
    """
    Raise if config.yaml split is malformed. The block is optional.

    Parameters
    ----------
    config : dict
        config.yaml.

    Returns
    -------
    None

    Raises
    ------
    ValueError
        If split is not a mapping, lacks a key, is_end is not a date after
        backtest_start, or embargo_sessions is shorter than one holding period.

    Examples
    --------
    >>> _check_split({"rebalance": "M"})
    >>> _check_split({"rebalance": "M",
    ...               "split": {"is_end": dt.date(2023, 12, 29), "embargo_sessions": 5}})
    Traceback (most recent call last):
    ...
    ValueError: config.yaml split.embargo_sessions must be an integer >= 21 for rebalance M
    """

    split = config.get("split")
    if split is None:
        return
    if not isinstance(split, dict):
        raise ValueError("config.yaml split must be a mapping with is_end and embargo_sessions")
    _require(split, REQUIRED_SPLIT, "config.yaml split")

    # is_end: a date after backtest_start
    is_end = split["is_end"]
    if not isinstance(is_end, dt.date):
        raise ValueError("config.yaml split.is_end must be a date, YYYY-MM-DD")
    start = config.get("backtest_start")
    if start is not None and is_end <= dt.date.fromisoformat(str(start)):
        raise ValueError("config.yaml split.is_end must be after backtest_start")

    # embargo_sessions: at least one holding period
    embargo = split["embargo_sessions"]
    floor = MIN_EMBARGO[config["rebalance"]]
    if isinstance(embargo, bool) or not isinstance(embargo, int) or embargo < floor:
        raise ValueError(f"config.yaml split.embargo_sessions must be an integer >= {floor} "
                         f"for rebalance {config['rebalance']}")

# %%
# Load

# Load and check a strategy folder
def load_strategy(name):
    """
    Load strategy/<name>, check its config and import its code.

    Parameters
    ----------
    name : str
        Folder name under strategy/.

    Returns
    -------
    strategy : Strategy
        The loaded strategy.

    Raises
    ------
    FileNotFoundError
        If the folder or config.yaml is missing.
    ValueError
        If a required key is missing, a value is not allowed (including
        the optional split block).
    TypeError
        If data.py or weights.py lacks its function.

    Examples
    --------
    >>> strategy = load_strategy("strategy_example")
    >>> strategy.name, strategy.config["rebalance"]
    ('strategy_example', 'M')
    >>> load_strategy("no_such_strategy")
    Traceback (most recent call last):
    ...
    FileNotFoundError: no strategy folder strategy/no_such_strategy
    """

    # Folder
    folder = STRATEGY_ROOT / name
    if not folder.is_dir():
        raise FileNotFoundError(f"no strategy folder strategy/{name}")

    # config.yaml
    config = _read_yaml(folder / "config.yaml")
    _require(config, REQUIRED_CONFIG, "config.yaml")
    if config["rebalance"] not in REBALANCE_RULES:
        raise ValueError(f"config.yaml rebalance must be one of {REBALANCE_RULES}")
    _check_split(config)

    # config.yaml paper block
    paper = config["paper"]
    if not isinstance(paper, dict):
        raise ValueError("config.yaml paper must be a mapping")
    _require(paper, REQUIRED_PAPER, "config.yaml paper")
    if not isinstance(paper["limits"], dict):
        raise ValueError("config.yaml paper.limits must be a mapping")
    _require(paper["limits"], REQUIRED_LIMITS, "config.yaml paper.limits")
    if paper.get("mode", "paper") != "paper":
        raise ValueError("config.yaml paper.mode must be 'paper'; real-money trading is not supported")
    if paper.get("broker", "alpaca") not in BROKERS:
        raise ValueError(f"config.yaml paper.broker must be one of {BROKERS}")

    # data.py and weights.py
    data = _import(folder / "data.py", f"fbs_strategy_{name}_data")
    weights = _import(folder / "weights.py", f"fbs_strategy_{name}_weights")
    if not callable(getattr(data, "fetch", None)):
        raise TypeError(f"strategy/{name}/data.py must define fetch(config, start, end)")
    if not callable(getattr(weights, "compute", None)):
        raise TypeError(f"strategy/{name}/weights.py must define compute(data, params)")

    strategy = Strategy(name=name, folder=folder, config=config, paper=paper, data=data, weights=weights)

    return strategy
