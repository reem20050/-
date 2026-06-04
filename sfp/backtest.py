"""Event-driven backtester for SFP signals.

The Pine indicator only *plots* signals; it never defines entries, stops or
targets. This module supplies a realistic, configurable trade model on top of
the signal stream so the system can actually be evaluated.

Trade model (one position at a time)
------------------------------------
* Entry: at the next bar's open (default, no look-ahead) or the signal bar's
  close.
* Stop: ``"sweep"`` (just beyond the liquidity extreme that was swept),
  ``"atr"`` (ATR multiple), or ``"pct"`` (fixed %).
* Target: ``"rr"`` (reward:risk multiple), ``"opposite"`` (exit on the next
  opposite signal), or ``"none"``. A ``max_hold_bars`` time-stop and end-of-data
  liquidation always apply.
* Intrabar: if both stop and target fall inside the same bar, ``stop_first``
  decides which is assumed to trigger (conservative default = stop).
* Sizing: each trade risks ``risk_frac`` of current equity, so the equity curve
  compounds in R-multiples and is independent of the instrument's nominal price.
* Costs: ``fee_pct`` is charged per side on notional.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict, Any, Optional

import numpy as np
import pandas as pd

from .indicator import SFPResult


@dataclass
class BacktestConfig:
    entry: str = "next_open"          # "next_open" | "close"
    stop_mode: str = "sweep"          # "sweep" | "atr" | "pct"
    stop_buffer_pct: float = 0.05     # extra % beyond the swept extreme (sweep mode)
    atr_period: int = 14
    atr_mult: float = 1.5
    stop_pct: float = 1.0             # % distance for "pct" mode
    target_mode: str = "rr"           # "rr" | "opposite" | "none"
    rr: float = 2.0
    max_hold_bars: int = 0            # 0 disables the time-stop
    exit_on_opposite: bool = True
    fee_pct: float = 0.0              # per-side cost, % of notional
    risk_frac: float = 0.01           # fraction of equity risked per trade
    initial_equity: float = 10_000.0
    stop_first: bool = True           # both hit same bar -> assume stop


def _atr(high, low, close, period):
    """Wilder's ATR as a numpy array aligned to the bars."""
    n = len(close)
    tr = np.empty(n)
    tr[0] = high[0] - low[0]
    for i in range(1, n):
        tr[i] = max(
            high[i] - low[i],
            abs(high[i] - close[i - 1]),
            abs(low[i] - close[i - 1]),
        )
    atr = np.full(n, np.nan)
    if n >= period:
        atr[period - 1] = tr[:period].mean()
        for i in range(period, n):
            atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period
    return atr


@dataclass
class BacktestResult:
    trades: pd.DataFrame
    equity_curve: pd.Series
    config: BacktestConfig

    @property
    def n_trades(self) -> int:
        return len(self.trades)


def _stop_price(direction, entry_price, sig, o, h, l, c, atr, entry_bar, cfg):
    """Compute the protective stop for a trade, or ``None`` if invalid."""
    if cfg.stop_mode == "sweep":
        sweep_bar = int(sig["sweep_bar"])
        sig_idx = int(sig["index"])
        lo_b = max(0, min(sweep_bar, sig_idx))
        hi_b = max(sweep_bar, sig_idx)
        if direction == 1:
            extreme = float(np.min(l[lo_b: hi_b + 1]))
            return extreme * (1.0 - cfg.stop_buffer_pct / 100.0)
        extreme = float(np.max(h[lo_b: hi_b + 1]))
        return extreme * (1.0 + cfg.stop_buffer_pct / 100.0)
    if cfg.stop_mode == "atr":
        a = atr[entry_bar]
        if np.isnan(a):
            return None
        return entry_price - direction * cfg.atr_mult * a
    if cfg.stop_mode == "pct":
        return entry_price * (1.0 - direction * cfg.stop_pct / 100.0)
    raise ValueError(f"unknown stop_mode {cfg.stop_mode!r}")


def run_backtest(
    result: SFPResult,
    config: Optional[BacktestConfig] = None,
) -> BacktestResult:
    """Simulate trades from indicator ``result`` under ``config``."""
    cfg = config or BacktestConfig()
    frame = result.frame
    o = frame["open"].to_numpy(float)
    h = frame["high"].to_numpy(float)
    l = frame["low"].to_numpy(float)
    c = frame["close"].to_numpy(float)
    N = len(frame)
    index = frame.index

    atr = _atr(h, l, c, cfg.atr_period) if cfg.stop_mode == "atr" else None

    # Map bar -> opposite-exit direction for fast lookup during the walk.
    sig_dir: Dict[int, int] = {int(s["index"]): int(s["direction"]) for s in result.signals}

    equity = cfg.initial_equity
    trades: List[Dict[str, Any]] = []
    eq_points = [(index[0] if N else 0, equity)]
    next_free_bar = 0

    for sig in result.signals:
        sig_idx = int(sig["index"])
        direction = int(sig["direction"])

        entry_bar = sig_idx + 1 if cfg.entry == "next_open" else sig_idx
        if entry_bar >= N:
            continue
        if entry_bar < next_free_bar:
            continue  # still inside a previous trade

        entry_price = o[entry_bar] if cfg.entry == "next_open" else c[sig_idx]

        stop_price = _stop_price(direction, entry_price, sig, o, h, l, c, atr, entry_bar, cfg)
        if stop_price is None:
            continue
        risk = (entry_price - stop_price) * direction
        if risk <= 0:
            # Degenerate stop (wrong side of entry) -> skip and log nothing.
            continue

        target_price = None
        if cfg.target_mode == "rr":
            target_price = entry_price + direction * cfg.rr * risk

        first_check = entry_bar if cfg.entry == "next_open" else entry_bar + 1

        exit_bar = N - 1
        exit_price = c[N - 1]
        reason = "eod"

        j = first_check
        while j < N:
            hit_stop = (l[j] <= stop_price) if direction == 1 else (h[j] >= stop_price)
            hit_tgt = False
            if target_price is not None:
                hit_tgt = (h[j] >= target_price) if direction == 1 else (l[j] <= target_price)

            if hit_stop and hit_tgt:
                if cfg.stop_first:
                    exit_bar, exit_price, reason = j, stop_price, "stop"
                else:
                    exit_bar, exit_price, reason = j, target_price, "target"
                break
            if hit_stop:
                exit_bar, exit_price, reason = j, stop_price, "stop"
                break
            if hit_tgt:
                exit_bar, exit_price, reason = j, target_price, "target"
                break
            if cfg.max_hold_bars > 0 and (j - entry_bar) >= cfg.max_hold_bars:
                exit_bar, exit_price, reason = j, c[j], "time"
                break
            if cfg.exit_on_opposite and j > entry_bar and sig_dir.get(j, 0) == -direction:
                exit_bar, exit_price, reason = j, c[j], "opposite"
                break
            j += 1

        # --- Sizing & PnL (risk-based) ---
        equity_at_entry = equity
        risk_amount = cfg.risk_frac * equity_at_entry
        size = risk_amount / risk
        gross_pnl = (exit_price - entry_price) * size * direction
        fees = (cfg.fee_pct / 100.0) * (entry_price + exit_price) * size
        net_pnl = gross_pnl - fees
        equity += net_pnl
        r_multiple = net_pnl / risk_amount if risk_amount else 0.0

        trades.append({
            "signal_bar": sig_idx,
            "entry_bar": entry_bar,
            "exit_bar": exit_bar,
            "entry_time": index[entry_bar],
            "exit_time": index[exit_bar],
            "direction": direction,
            "entry_price": entry_price,
            "stop_price": stop_price,
            "target_price": target_price if target_price is not None else np.nan,
            "exit_price": exit_price,
            "exit_reason": reason,
            "risk_per_unit": risk,
            "R": r_multiple,
            "pnl": net_pnl,
            "equity": equity,
            "bars_held": exit_bar - entry_bar,
        })
        eq_points.append((index[exit_bar], equity))
        next_free_bar = exit_bar + 1

    trades_df = pd.DataFrame(trades)
    if len(eq_points) > 1:
        times = [t for t, _ in eq_points]
        vals = [v for _, v in eq_points]
        equity_curve = pd.Series(vals, index=pd.Index(times, name="time"))
    else:
        equity_curve = pd.Series([cfg.initial_equity], index=[index[0] if N else 0])

    return BacktestResult(trades=trades_df, equity_curve=equity_curve, config=cfg)
