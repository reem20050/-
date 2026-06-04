"""Faithful Python port of the *Swing Failure Signals [AlgoAlpha]* Pine v6 indicator.

The goal of this module is fidelity, not elegance: it reproduces the original
Pine Script bar-by-bar state machine as closely as Python allows so that the
backtester sits on top of the *same* signals a TradingView user would see.

Pine -> Python translation notes
---------------------------------
* Pine executes the script once per bar, left to right. ``var`` variables
  persist across bars; non-``var`` variables reset every bar. We emulate this
  with a single forward loop over the OHLC arrays.
* Pine series access ``close[i]`` means "the close ``i`` bars ago". We expose
  this through ``cl(n, i) -> closes[n - i]`` (returns ``nan`` before history
  start, which mirrors Pine's ``na`` and makes comparisons evaluate to False).
* Pine arrays use ``unshift`` (push front), ``pop`` (remove last),
  ``shift`` (remove first), ``get(i)``, ``remove(i)``. We map these to plain
  Python list operations (``insert(0, x)``, ``pop()``, ``pop(0)``, ``[i]``,
  ``del l[i]``).
* ``ta.pivothigh(len, len)`` confirms, on bar ``p + len``, a pivot located at
  bar ``p``; its value equals ``high[p]``. We pre-compute these series with
  strict ``>`` / ``<`` comparisons on both sides (the common interpretation;
  ties break the pivot). See ``KNOWN FIDELITY NOTES`` in the README.

Important quirk preserved from the source: the indicator stores the
*confirmation* ``bar_index`` (``n``) alongside each pivot price, not the bar
where the pivot actually printed (``n - len``). The ``len_`` distance check and
the drawing offsets in the original rely on this, so we keep it identical.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict, Any

import numpy as np
import pandas as pd


@dataclass
class SFPParams:
    """Indicator inputs, mirroring the Pine ``input.*`` calls.

    Attributes map to the original names as follows:
        pivot_len  -> ``len``        (Pivot Detection Length, default 12)
        max_edge   -> ``len_``       (Max Pivot Point Edge, default 50)
        patience   -> ``patience``   (default 7)
        tolerance  -> ``tolerence``  (Trend Noise Filter, default 0.7)
    """

    pivot_len: int = 12
    max_edge: int = 50
    patience: int = 7
    tolerance: float = 0.7


def pivot_high(high: np.ndarray, length: int) -> np.ndarray:
    """Replicate ``ta.pivothigh(length, length)``.

    Returns an array where index ``n`` holds the pivot-high *price* confirmed on
    bar ``n`` (i.e. ``high[n - length]``) or ``nan`` if bar ``n`` does not
    confirm a pivot.
    """
    n = len(high)
    out = np.full(n, np.nan)
    for p in range(length, n - length):
        hp = high[p]
        is_piv = True
        for k in range(1, length + 1):
            if not (hp > high[p - k] and hp > high[p + k]):
                is_piv = False
                break
        if is_piv:
            out[p + length] = hp
    return out


def pivot_low(low: np.ndarray, length: int) -> np.ndarray:
    """Replicate ``ta.pivotlow(length, length)`` (symmetric to ``pivot_high``)."""
    n = len(low)
    out = np.full(n, np.nan)
    for p in range(length, n - length):
        lp = low[p]
        is_piv = True
        for k in range(1, length + 1):
            if not (lp < low[p - k] and lp < low[p + k]):
                is_piv = False
                break
        if is_piv:
            out[p + length] = lp
    return out


@dataclass
class SFPResult:
    """Output of :func:`run`.

    ``frame`` is aligned to the input index and carries the per-bar series
    (``bullsfp``, ``bearsfp``, ``trend``, ``cisd``, ``sfp_trend_state``,
    ``cisd_level``). ``signals`` is a list of dicts with everything the
    backtester needs to size and manage a trade.
    """

    frame: pd.DataFrame
    signals: List[Dict[str, Any]]


def run(df: pd.DataFrame, params: SFPParams | None = None) -> SFPResult:
    """Run the indicator over an OHLC dataframe.

    ``df`` must contain lowercase columns ``open``, ``high``, ``low``, ``close``
    (use :func:`sfp.data.normalize_ohlc`). The index is preserved on the output.
    """
    if params is None:
        params = SFPParams()

    o = df["open"].to_numpy(dtype=float)
    h = df["high"].to_numpy(dtype=float)
    l = df["low"].to_numpy(dtype=float)
    c = df["close"].to_numpy(dtype=float)
    N = len(df)

    L = params.pivot_len
    max_edge = params.max_edge
    patience = params.patience
    tol = params.tolerance

    pivh = pivot_high(h, L)
    pivl = pivot_low(l, L)

    # --- var arrays / state (persist across bars) ---
    pivhs: List[float] = []        # [idx, price, idx, price, ...] newest at front
    pivls: List[float] = []
    temp_bull: List[float] = []    # [pivot_idx, pivot_price, sweep_bar] (latest)
    temp_bear: List[float] = []
    bear_potential: List[float] = []  # [open, idx, ...] bullish-flip candles
    bull_potential: List[float] = []  # [open, idx, ...] bearish-flip candles

    bar_sweep_bull = 0
    bar_sweep_bear = 0
    cisd_level = np.nan
    cisd_idx = np.nan
    trend = 0
    sfp_trend_state = 0

    # --- output series ---
    out_bull = np.zeros(N, dtype=bool)
    out_bear = np.zeros(N, dtype=bool)
    out_trend = np.zeros(N, dtype=int)
    out_cisd = np.zeros(N, dtype=int)
    out_state = np.zeros(N, dtype=int)
    out_cisd_level = np.full(N, np.nan)
    signals: List[Dict[str, Any]] = []

    def cl(n: int, i: int) -> float:
        j = n - i
        return c[j] if j >= 0 else np.nan

    def op(n: int, i: int) -> float:
        j = n - i
        return o[j] if j >= 0 else np.nan

    for n in range(N):
        bullsfp = False
        bearsfp = False
        cisd = 0

        # --- Array Population ---
        if not np.isnan(pivh[n]):
            pivhs.insert(0, pivh[n])
            pivhs.insert(0, float(n))
        if not np.isnan(pivl[n]):
            pivls.insert(0, pivl[n])
            pivls.insert(0, float(n))

        # --- Array Maintenance ---
        while len(pivhs) > 100:
            pivhs.pop()
            pivhs.pop()
        while len(pivls) > 100:
            pivls.pop()
            pivls.pop()
        while len(temp_bull) > 3:
            temp_bull.pop()
        while len(temp_bear) > 3:
            temp_bear.pop()

        # --- Sweep Detection (Bearish): current high takes out a stored swing high ---
        if len(pivhs) > 1:
            lvl = 0.0
            for i in range(len(pivhs) - 1, 0, -2):
                if i < len(pivhs):
                    pivot_price = pivhs[i]
                    pivot_idx = pivhs[i - 1]
                    if h[n] > pivot_price:
                        if n - pivot_idx < max_edge:
                            if pivot_price > lvl:
                                lvl = pivot_price
                            temp_bear.insert(0, float(n))
                            temp_bear.insert(0, pivot_price)
                            temp_bear.insert(0, pivot_idx)
                        del pivhs[i]
                        del pivhs[i - 1]
            if lvl != 0.0:
                bar_sweep_bear = n

        # --- Sweep Detection (Bullish): current low takes out a stored swing low ---
        if len(pivls) > 1:
            lvl = 0.0
            for i in range(len(pivls) - 1, 0, -2):
                if i < len(pivls):
                    pivot_price = pivls[i]
                    pivot_idx = pivls[i - 1]
                    if l[n] < pivot_price:
                        if n - pivot_idx < max_edge:
                            if pivot_price < lvl or lvl == 0:
                                lvl = pivot_price
                            temp_bull.insert(0, float(n))
                            temp_bull.insert(0, pivot_price)
                            temp_bull.insert(0, pivot_idx)
                        del pivls[i]
                        del pivls[i - 1]
            if lvl != 0.0:
                bar_sweep_bull = n

        # --- CISD candle-flip recording ---
        if cl(n, 1) < op(n, 1) and c[n] > o[n]:
            bear_potential.insert(0, float(n))
            bear_potential.insert(0, o[n])
        if cl(n, 1) > op(n, 1) and c[n] < o[n]:
            bull_potential.insert(0, float(n))
            bull_potential.insert(0, o[n])

        # --- CISD down (cisd = 1): a failed bullish flip ---
        if len(bear_potential) > 0:
            inloop = True
            while inloop and len(bear_potential) > 0:
                p_idx = bear_potential[1]
                p_val = bear_potential[0]
                if c[n] < p_val:
                    highest = 0.0
                    len_check = n - int(p_idx)
                    if 0 <= len_check < 4999:
                        for i in range(0, len_check + 1):
                            ci = cl(n, i)
                            if ci > highest:
                                highest = ci
                        running = True
                        init = len_check + 1
                        top = 0.0
                        while running and init < 4999:
                            ci = cl(n, init)
                            oi = op(n, init)
                            if ci < oi:
                                top = oi
                                init += 1
                            else:
                                running = False
                        denom = top - p_val
                        if denom != 0 and (highest - p_val) / denom > tol:
                            cisd_level = p_val
                            cisd_idx = int(p_idx)
                            bear_potential.clear()
                            cisd = 1
                            inloop = False
                        else:
                            bear_potential.pop(0)
                            bear_potential.pop(0)
                    else:
                        bear_potential.pop(0)
                        bear_potential.pop(0)
                else:
                    inloop = False

        # --- CISD up (cisd = 2): a failed bearish flip ---
        if len(bull_potential) > 0:
            inloop = True
            while inloop and len(bull_potential) > 0:
                p_idx = bull_potential[1]
                p_val = bull_potential[0]
                if c[n] > p_val:
                    lowest = c[n]
                    len_check = n - int(p_idx)
                    if 0 <= len_check < 4999:
                        for i in range(0, len_check + 1):
                            ci = cl(n, i)
                            if ci < lowest:
                                lowest = ci
                        running = True
                        init = len_check + 1
                        bottom = 0.0
                        while running and init < 4999:
                            ci = cl(n, init)
                            oi = op(n, init)
                            if ci > oi:
                                bottom = oi
                                init += 1
                            else:
                                running = False
                        denom = p_val - bottom
                        if denom != 0 and (p_val - lowest) / denom > tol:
                            cisd_level = p_val
                            cisd_idx = int(p_idx)
                            bull_potential.clear()
                            cisd = 2
                            inloop = False
                        else:
                            bull_potential.pop(0)
                            bull_potential.pop(0)
                    else:
                        bull_potential.pop(0)
                        bull_potential.pop(0)
                else:
                    inloop = False

        # --- Trend & signal generation ---
        prev_trend = trend
        if cisd == 1:
            trend = -1
        elif cisd == 2:
            trend = 1
        crossover = prev_trend <= 0 and trend > 0
        crossunder = prev_trend >= 0 and trend < 0
        if crossover and (n - bar_sweep_bull < patience):
            bullsfp = True
        if crossunder and (n - bar_sweep_bear < patience):
            bearsfp = True

        # --- Record signal metadata for the backtester ---
        if bullsfp:
            swept_level = temp_bull[1] if len(temp_bull) >= 3 else np.nan
            sweep_bar = int(temp_bull[2]) if len(temp_bull) >= 3 else n
            signals.append({
                "index": n,
                "direction": 1,
                "entry_close": c[n],
                "swept_level": swept_level,
                "sweep_bar": sweep_bar,
                "cisd_level": cisd_level,
                "cisd_idx": cisd_idx,
            })
        if bearsfp:
            swept_level = temp_bear[1] if len(temp_bear) >= 3 else np.nan
            sweep_bar = int(temp_bear[2]) if len(temp_bear) >= 3 else n
            signals.append({
                "index": n,
                "direction": -1,
                "entry_close": c[n],
                "swept_level": swept_level,
                "sweep_bar": sweep_bar,
                "cisd_level": cisd_level,
                "cisd_idx": cisd_idx,
            })

        # --- Bar-coloring state machine ---
        if bullsfp:
            sfp_trend_state = 1
        elif bearsfp:
            sfp_trend_state = -1
        else:
            if sfp_trend_state == 1 and trend == -1:
                sfp_trend_state = 0
            elif sfp_trend_state == -1 and trend == 1:
                sfp_trend_state = 0

        out_bull[n] = bullsfp
        out_bear[n] = bearsfp
        out_trend[n] = trend
        out_cisd[n] = cisd
        out_state[n] = sfp_trend_state
        out_cisd_level[n] = cisd_level

    frame = pd.DataFrame(
        {
            "open": o,
            "high": h,
            "low": l,
            "close": c,
            "bullsfp": out_bull,
            "bearsfp": out_bear,
            "trend": out_trend,
            "cisd": out_cisd,
            "sfp_trend_state": out_state,
            "cisd_level": out_cisd_level,
        },
        index=df.index,
    )
    return SFPResult(frame=frame, signals=signals)
