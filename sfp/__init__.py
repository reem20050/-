"""SFP research toolkit.

A faithful Python port of the *Swing Failure Signals [AlgoAlpha]* Pine v6
indicator plus a backtesting / parameter-sweep workflow for investigating it.

Quick start
-----------
    from sfp import synthetic_ohlc, SFPParams, run_indicator
    from sfp import BacktestConfig, run_backtest, compute_metrics, format_metrics

    df = synthetic_ohlc(1500, seed=7)
    res = run_indicator(df, SFPParams())
    bt = run_backtest(res, BacktestConfig(rr=2.0))
    print(format_metrics(compute_metrics(bt)))
"""

from .indicator import SFPParams, SFPResult, run as run_indicator, pivot_high, pivot_low
from .data import load_csv, load_yfinance, synthetic_ohlc, normalize_ohlc
from .backtest import BacktestConfig, BacktestResult, run_backtest
from .metrics import compute_metrics, format_metrics
from .optimize import grid_search, default_score

__all__ = [
    "SFPParams", "SFPResult", "run_indicator", "pivot_high", "pivot_low",
    "load_csv", "load_yfinance", "synthetic_ohlc", "normalize_ohlc",
    "BacktestConfig", "BacktestResult", "run_backtest",
    "compute_metrics", "format_metrics",
    "grid_search", "default_score",
]
