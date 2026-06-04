"""Headless (Agg) matplotlib charts for the SFP workflow.

Two plots:
* :func:`plot_signals` - price with bullish/bearish SFP markers, swept levels and
  CISD lines (optionally limited to the last ``n_bars`` for readability).
* :func:`plot_equity`  - the backtest equity curve with drawdown shading.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("Agg")  # no display in the sandbox
import matplotlib.pyplot as plt  # noqa: E402

from .indicator import SFPResult
from .backtest import BacktestResult


def plot_signals(
    result: SFPResult,
    path: str,
    n_bars: Optional[int] = 400,
    title: str = "Swing Failure Signals",
) -> str:
    """Render price + signals to ``path`` (PNG). Returns ``path``."""
    frame = result.frame
    if n_bars is not None and len(frame) > n_bars:
        frame = frame.iloc[-n_bars:]
    start = frame.index[0]
    end = frame.index[-1]

    fig, ax = plt.subplots(figsize=(14, 7))
    x = np.arange(len(frame))
    ax.plot(x, frame["close"].to_numpy(), color="#444", lw=0.9, label="Close")

    # Light high/low band for context.
    ax.fill_between(x, frame["low"].to_numpy(), frame["high"].to_numpy(),
                    color="#888", alpha=0.12, lw=0)

    bull = frame["bullsfp"].to_numpy()
    bear = frame["bearsfp"].to_numpy()
    ax.scatter(x[bull], frame["low"].to_numpy()[bull], marker="^",
               color="#00b386", s=90, zorder=5, label="Bullish SFP")
    ax.scatter(x[bear], frame["high"].to_numpy()[bear], marker="v",
               color="#ff1100", s=90, zorder=5, label="Bearish SFP")

    ax.set_title(f"{title}  ({start} -> {end})")
    ax.set_xlabel("bar")
    ax.set_ylabel("price")
    ax.legend(loc="best")
    ax.grid(alpha=0.2)
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)
    return path


def plot_equity(result: BacktestResult, path: str,
                title: str = "SFP equity curve") -> str:
    """Render the equity curve + drawdown to ``path`` (PNG). Returns ``path``."""
    eq = result.equity_curve
    vals = eq.to_numpy(float)
    peak = np.maximum.accumulate(vals)
    dd = (vals - peak) / peak * 100.0

    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(13, 8), sharex=True, gridspec_kw={"height_ratios": [3, 1]}
    )
    x = np.arange(len(vals))
    ax1.plot(x, vals, color="#1f77b4", lw=1.3)
    ax1.set_ylabel("equity")
    ax1.set_title(title)
    ax1.grid(alpha=0.2)

    ax2.fill_between(x, dd, 0, color="#ff1100", alpha=0.4)
    ax2.set_ylabel("drawdown %")
    ax2.set_xlabel("trade #")
    ax2.grid(alpha=0.2)

    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)
    return path
