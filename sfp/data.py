"""Data sources for the SFP research workflow.

Three ways to get OHLC data into the backtester:

1. :func:`load_csv`      - your own exported history (most common / reliable).
2. :func:`load_yfinance` - convenience wrapper around the ``yfinance`` package.
                           NOTE: blocked in the sandboxed Claude Code web env
                           ("Host not in allowlist"); works on a normal machine.
3. :func:`synthetic_ohlc`- deterministic generator that produces realistic swing
                           structure *and* liquidity sweeps, so the whole
                           pipeline can be exercised offline / in tests.

Every loader returns a dataframe with a ``DatetimeIndex`` (when available) and
lowercase columns ``open, high, low, close`` (+ ``volume`` if present), i.e. the
shape the indicator and backtester expect.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd


_OHLC_ALIASES = {
    "open": "open", "o": "open",
    "high": "high", "h": "high",
    "low": "low", "l": "low",
    "close": "close", "c": "close", "adj close": "close", "adj_close": "close",
    "price": "close",
    "volume": "volume", "vol": "volume", "v": "volume",
}


def normalize_ohlc(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy with canonical lowercase ``open/high/low/close[/volume]``.

    Accepts case-insensitive and aliased column names. Raises ``ValueError`` if
    any of the four OHLC columns cannot be resolved.
    """
    # Flatten a possible MultiIndex (yfinance returns one for single tickers too).
    if isinstance(df.columns, pd.MultiIndex):
        df = df.copy()
        df.columns = [
            next((str(x) for x in tup if str(x) != ""), "") for tup in df.columns
        ]

    rename = {}
    for col in df.columns:
        key = str(col).strip().lower()
        if key in _OHLC_ALIASES:
            rename[col] = _OHLC_ALIASES[key]
    out = df.rename(columns=rename)

    # If duplicates were produced (e.g. both 'Close' and 'Adj Close' -> close),
    # keep the first occurrence.
    out = out.loc[:, ~out.columns.duplicated()]

    missing = [c for c in ("open", "high", "low", "close") if c not in out.columns]
    if missing:
        raise ValueError(
            f"Could not find OHLC columns {missing}; got {list(df.columns)}"
        )

    keep = ["open", "high", "low", "close"]
    if "volume" in out.columns:
        keep.append("volume")
    out = out[keep].astype(float)
    out = out.dropna(subset=["open", "high", "low", "close"]).reset_index(drop=False)
    # Preserve a datetime index if the original index looked like dates.
    idx_col = out.columns[0]
    try:
        out[idx_col] = pd.to_datetime(out[idx_col])
        out = out.set_index(idx_col)
        out.index.name = "datetime"
    except (ValueError, TypeError):
        out = out.drop(columns=[idx_col])
        out.index.name = "bar"
    return out


def load_csv(path: str, **read_csv_kwargs) -> pd.DataFrame:
    """Load OHLC data from a CSV file and normalize it."""
    df = pd.read_csv(path, **read_csv_kwargs)
    return normalize_ohlc(df)


def load_yfinance(
    ticker: str,
    period: str = "2y",
    interval: str = "1d",
    **kwargs,
) -> pd.DataFrame:
    """Download OHLC data via ``yfinance`` and normalize it.

    Raises a clear ``RuntimeError`` when the network is unavailable (e.g. the
    Claude Code web sandbox blocks Yahoo). Use :func:`load_csv` or
    :func:`synthetic_ohlc` in that case.
    """
    try:
        import yfinance as yf
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError(
            "yfinance is not installed. `pip install yfinance` or use load_csv()."
        ) from exc

    df = yf.download(
        ticker, period=period, interval=interval, progress=False,
        auto_adjust=True, **kwargs,
    )
    if df is None or len(df) == 0:
        raise RuntimeError(
            f"yfinance returned no rows for {ticker!r}. In sandboxed environments "
            "Yahoo is typically blocked ('Host not in allowlist'); export a CSV "
            "and use load_csv(), or generate synthetic_ohlc() data instead."
        )
    return normalize_ohlc(df)


def synthetic_ohlc(
    n: int = 1500,
    seed: int = 7,
    start_price: float = 100.0,
    base_vol: float = 0.012,
    sweep_prob: float = 0.06,
    freq: str = "D",
) -> pd.DataFrame:
    """Generate deterministic OHLC bars with swing structure and liquidity sweeps.

    The generator runs a regime-switching random walk (alternating drift so that
    swing highs/lows form) and, with probability ``sweep_prob`` per bar, injects a
    wick that pokes just beyond the recent ``~20``-bar extreme before the bar
    closes back inside it -- the classic stop-run that the SFP indicator hunts
    for. This guarantees the full signal -> backtest pipeline has something to
    chew on without any network access.

    Returns a dataframe indexed by a synthetic business-day ``DatetimeIndex``.
    """
    rng = np.random.default_rng(seed)

    close = np.empty(n)
    open_ = np.empty(n)
    high = np.empty(n)
    low = np.empty(n)

    price = start_price
    drift = 0.0008
    regime_len = 0
    prev_close = start_price

    recent_high = start_price
    recent_low = start_price
    window = 20

    closes_hist: list[float] = []

    for i in range(n):
        # Regime switching: flip drift sign every ~40-90 bars to build swings.
        if regime_len <= 0:
            drift = rng.choice([1.0, -1.0]) * rng.uniform(0.0004, 0.0016)
            regime_len = rng.integers(40, 90)
        regime_len -= 1

        vol = base_vol * (0.6 + 0.8 * abs(rng.standard_normal()))
        ret = drift + vol * rng.standard_normal()
        o = prev_close
        c = o * (1.0 + ret)

        body_hi = max(o, c)
        body_lo = min(o, c)
        up_wick = body_hi * (1.0 + abs(rng.normal(0, vol * 0.6)))
        dn_wick = body_lo * (1.0 - abs(rng.normal(0, vol * 0.6)))

        # Inject a liquidity sweep: poke beyond the recent extreme, close back in.
        if i > window and rng.random() < sweep_prob:
            if rng.random() < 0.5:
                # Sweep the recent low, then close back above it.
                target = recent_low * (1.0 - rng.uniform(0.001, 0.006))
                dn_wick = min(dn_wick, target)
                c = max(c, recent_low * (1.0 + rng.uniform(0.0, 0.004)))
            else:
                # Sweep the recent high, then close back below it.
                target = recent_high * (1.0 + rng.uniform(0.001, 0.006))
                up_wick = max(up_wick, target)
                c = min(c, recent_high * (1.0 - rng.uniform(0.0, 0.004)))
            body_hi = max(o, c)
            body_lo = min(o, c)

        hi = max(body_hi, up_wick)
        lo = min(body_lo, dn_wick)

        open_[i] = o
        close[i] = c
        high[i] = hi
        low[i] = lo

        prev_close = c
        price = c

        closes_hist.append(c)
        if len(closes_hist) > window:
            seg_hi = high[max(0, i - window + 1): i + 1]
            seg_lo = low[max(0, i - window + 1): i + 1]
            recent_high = float(np.max(seg_hi))
            recent_low = float(np.min(seg_lo))
        else:
            recent_high = max(recent_high, hi)
            recent_low = min(recent_low, lo)

    idx = pd.bdate_range("2018-01-01", periods=n, freq=freq if freq != "D" else "B")
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close},
        index=idx,
    )
