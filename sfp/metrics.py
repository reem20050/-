"""Performance metrics computed from a :class:`~sfp.backtest.BacktestResult`."""

from __future__ import annotations

from typing import Dict, Any

import numpy as np
import pandas as pd

from .backtest import BacktestResult


def _max_drawdown(equity: np.ndarray) -> float:
    """Maximum peak-to-trough drawdown as a positive fraction (0.2 == -20%)."""
    if len(equity) == 0:
        return 0.0
    peak = np.maximum.accumulate(equity)
    dd = (equity - peak) / peak
    return float(-dd.min())


def _max_consecutive(mask: np.ndarray) -> int:
    best = run = 0
    for x in mask:
        run = run + 1 if x else 0
        best = max(best, run)
    return best


def compute_metrics(result: BacktestResult) -> Dict[str, Any]:
    """Return a flat dict of headline performance statistics."""
    tr = result.trades
    cfg = result.config
    if len(tr) == 0:
        return {
            "n_trades": 0, "win_rate": float("nan"), "expectancy_R": float("nan"),
            "total_R": 0.0, "profit_factor": float("nan"),
            "total_return_pct": 0.0, "max_drawdown_pct": 0.0,
            "final_equity": cfg.initial_equity,
        }

    R = tr["R"].to_numpy(float)
    pnl = tr["pnl"].to_numpy(float)
    wins = R > 0
    losses = R < 0

    gross_win = pnl[pnl > 0].sum()
    gross_loss = -pnl[pnl < 0].sum()
    profit_factor = (gross_win / gross_loss) if gross_loss > 0 else float("inf")

    equity = np.concatenate([[cfg.initial_equity], tr["equity"].to_numpy(float)])
    total_return = equity[-1] / cfg.initial_equity - 1.0

    # Per-trade return on equity, for a (trade-based) Sharpe-like ratio.
    ret = np.diff(equity) / equity[:-1]
    sharpe = float(ret.mean() / ret.std() * np.sqrt(len(ret))) if ret.std() > 0 else float("nan")

    avg_win = float(R[wins].mean()) if wins.any() else 0.0
    avg_loss = float(R[losses].mean()) if losses.any() else 0.0

    metrics: Dict[str, Any] = {
        "n_trades": int(len(tr)),
        "n_wins": int(wins.sum()),
        "n_losses": int(losses.sum()),
        "win_rate": float(wins.mean()),
        "expectancy_R": float(R.mean()),
        "total_R": float(R.sum()),
        "avg_win_R": avg_win,
        "avg_loss_R": avg_loss,
        "payoff_ratio": float(avg_win / abs(avg_loss)) if avg_loss != 0 else float("inf"),
        "profit_factor": float(profit_factor),
        "total_return_pct": float(total_return * 100.0),
        "final_equity": float(equity[-1]),
        "max_drawdown_pct": float(_max_drawdown(equity) * 100.0),
        "sharpe_trade": sharpe,
        "max_consec_wins": _max_consecutive(wins),
        "max_consec_losses": _max_consecutive(losses),
        "avg_bars_held": float(tr["bars_held"].mean()),
        "n_long": int((tr["direction"] == 1).sum()),
        "n_short": int((tr["direction"] == -1).sum()),
        "long_win_rate": float((tr.loc[tr["direction"] == 1, "R"] > 0).mean())
        if (tr["direction"] == 1).any() else float("nan"),
        "short_win_rate": float((tr.loc[tr["direction"] == -1, "R"] > 0).mean())
        if (tr["direction"] == -1).any() else float("nan"),
    }
    # Exit-reason breakdown.
    for reason, cnt in tr["exit_reason"].value_counts().items():
        metrics[f"exit_{reason}"] = int(cnt)
    return metrics


def format_metrics(metrics: Dict[str, Any]) -> str:
    """Human-readable, aligned text block for a metrics dict."""
    order = [
        "n_trades", "n_long", "n_short", "win_rate", "long_win_rate",
        "short_win_rate", "expectancy_R", "total_R", "avg_win_R", "avg_loss_R",
        "payoff_ratio", "profit_factor", "total_return_pct", "final_equity",
        "max_drawdown_pct", "sharpe_trade", "max_consec_wins",
        "max_consec_losses", "avg_bars_held",
    ]
    lines = []
    for key in order:
        if key in metrics:
            val = metrics[key]
            if isinstance(val, float):
                lines.append(f"  {key:<20} {val:>12.4f}")
            else:
                lines.append(f"  {key:<20} {val:>12}")
    extras = sorted(k for k in metrics if k.startswith("exit_"))
    if extras:
        lines.append("  --- exit reasons ---")
        for key in extras:
            lines.append(f"  {key:<20} {metrics[key]:>12}")
    return "\n".join(lines)
