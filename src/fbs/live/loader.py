"""Load a strategy folder: config.yaml, paper.yaml, data.py, weights.py."""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
STRATEGY_ROOT = REPO_ROOT / "strategy"

REQUIRED_CONFIG = ("name", "universe", "rebalance", "lookback_sessions", "params")
REQUIRED_PAPER = ("enabled", "account", "capital", "limits")
REQUIRED_LIMITS = ("max_gross", "max_net", "max_weight", "max_turnover",
                   "max_order_notional", "max_orders", "min_order_notional", "allow_shorts")
REBALANCE_RULES = ("D", "W", "M")


@dataclass(frozen=True)
class Strategy:
    name: str
    folder: Path
    config: dict
    paper: dict
    data: ModuleType       # must define fetch(config, start, end) -> DataFrame indexed by date
    weights: ModuleType    # must define compute(data, params) -> DataFrame (dates x symbols)


def _import(path: Path, module_name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _read_yaml(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"missing {path.relative_to(REPO_ROOT)}")
    with path.open() as f:
        return yaml.safe_load(f) or {}


def _require(mapping: dict, keys: tuple[str, ...], where: str) -> None:
    missing = [k for k in keys if k not in mapping]
    if missing:
        raise ValueError(f"{where} is missing keys: {', '.join(missing)}")


def load_strategy(name: str) -> Strategy:
    folder = STRATEGY_ROOT / name
    if not folder.is_dir():
        raise FileNotFoundError(f"no strategy folder strategy/{name}")

    config = _read_yaml(folder / "config.yaml")
    paper = _read_yaml(folder / "paper.yaml")
    _require(config, REQUIRED_CONFIG, "config.yaml")
    _require(paper, REQUIRED_PAPER, "paper.yaml")
    _require(paper["limits"], REQUIRED_LIMITS, "paper.yaml limits")
    if config["rebalance"] not in REBALANCE_RULES:
        raise ValueError(f"config.yaml rebalance must be one of {REBALANCE_RULES}")
    if paper.get("mode", "paper") != "paper":
        raise ValueError("paper.yaml mode must be 'paper'; real-money trading is not supported")

    data = _import(folder / "data.py", f"fbs_strategy_{name}_data")
    weights = _import(folder / "weights.py", f"fbs_strategy_{name}_weights")
    if not callable(getattr(data, "fetch", None)):
        raise TypeError(f"strategy/{name}/data.py must define fetch(config, start, end)")
    if not callable(getattr(weights, "compute", None)):
        raise TypeError(f"strategy/{name}/weights.py must define compute(data, params)")

    return Strategy(name=name, folder=folder, config=config, paper=paper, data=data, weights=weights)
