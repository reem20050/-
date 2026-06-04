"""Parameter sweep / grid search for the SFP system.

Runs the indicator + backtest for every combination in a parameter grid and
returns a tidy dataframe of metrics, sorted by a scoring function. This is the
core "investigation" loop: it surfaces which parameter regions are robust vs.
which look like noise / overfitting.
"""

from __future__ import annotations

import itertools
from dataclasses import replace
from typing import Dict, List, Iterable, Callable, Optional

import numpy as np
import pandas as pd

from .indicator import SFPParams, run as run_indicator
from .backtest import BacktestConfig, run_backtest
from .metrics import compute_metrics


def default_score(m: Dict) -> float:
    """Robustness-leaning objective: expectancy weighted by sqrt(#trades).

    Rewards a positive edge that repeats over many trades and penalises samples
    too small to trust. Returns ``-inf`` for empty / degenerate runs.
    """
    n = m.get("n_trades", 0)
    if n < 5:
        return float("-inf")
    exp = m.get("expectancy_R", float("nan"))
    if not np.isfinite(exp):
        return float("-inf")
    return exp * np.sqrt(n)


# Parameters that belong to the indicator vs. the backtest config.
_IND_KEYS = {"pivot_len", "max_edge", "patience", "tolerance"}


def grid_search(
    df: pd.DataFrame,
    param_grid: Dict[str, Iterable],
    base_indicator: Optional[SFPParams] = None,
    base_config: Optional[BacktestConfig] = None,
    score_fn: Callable[[Dict], float] = default_score,
) -> pd.DataFrame:
    """Sweep ``param_grid`` and return a metrics dataframe sorted by score.

    Grid keys may target either the indicator (``pivot_len``, ``max_edge``,
    ``patience``, ``tolerance``) or the backtest config (any
    :class:`BacktestConfig` field, e.g. ``rr``, ``stop_mode``, ``max_hold_bars``).
    """
    base_indicator = base_indicator or SFPParams()
    base_config = base_config or BacktestConfig()

    keys = list(param_grid.keys())
    combos = list(itertools.product(*(list(param_grid[k]) for k in keys)))

    rows: List[Dict] = []
    # Cache indicator runs: only re-run the (expensive) indicator when an
    # indicator-affecting parameter changes.
    ind_cache: Dict[tuple, object] = {}

    for combo in combos:
        overrides = dict(zip(keys, combo))
        ind_over = {k: v for k, v in overrides.items() if k in _IND_KEYS}
        cfg_over = {k: v for k, v in overrides.items() if k not in _IND_KEYS}

        ind_params = replace(base_indicator, **ind_over)
        ind_key = (ind_params.pivot_len, ind_params.max_edge,
                   ind_params.patience, ind_params.tolerance)
        if ind_key not in ind_cache:
            ind_cache[ind_key] = run_indicator(df, ind_params)
        ind_result = ind_cache[ind_key]

        cfg = replace(base_config, **cfg_over)
        bt = run_backtest(ind_result, cfg)
        m = compute_metrics(bt)
        m = dict(m)
        m.update(overrides)
        m["score"] = score_fn(m)
        rows.append(m)

    out = pd.DataFrame(rows)
    lead = keys + ["score", "n_trades", "win_rate", "expectancy_R",
                   "profit_factor", "total_return_pct", "max_drawdown_pct"]
    lead = [c for c in lead if c in out.columns]
    rest = [c for c in out.columns if c not in lead]
    out = out[lead + rest].sort_values("score", ascending=False).reset_index(drop=True)
    return out
