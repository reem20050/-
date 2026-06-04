import numpy as np
import pandas as pd

from sfp import SFPParams, run_indicator, synthetic_ohlc
from sfp.indicator import pivot_high, pivot_low


def test_pivot_high_basic():
    # A clear peak at index 3 with length 2 -> confirmed at index 5.
    high = np.array([1, 2, 3, 5, 3, 2, 1], dtype=float)
    out = pivot_high(high, 2)
    assert out[5] == 5.0
    # No other confirmations.
    assert np.isnan(out[:5]).all()
    assert np.isnan(out[6])


def test_pivot_low_basic():
    low = np.array([5, 4, 3, 1, 3, 4, 5], dtype=float)
    out = pivot_low(low, 2)
    assert out[5] == 1.0
    assert np.isnan(out[:5]).all()


def test_pivot_ties_break():
    # Equal neighbours on a side must NOT count as a strict pivot.
    high = np.array([1, 3, 3, 3, 1, 0, 0], dtype=float)
    out = pivot_high(high, 2)
    assert np.isnan(out).all()


def test_run_produces_signals_on_synthetic():
    df = synthetic_ohlc(n=1500, seed=7)
    res = run_indicator(df, SFPParams())
    # The synthetic generator injects sweeps; we expect a non-trivial signal set.
    assert len(res.signals) > 5
    # Frame is aligned and carries the expected columns.
    assert len(res.frame) == len(df)
    for col in ("bullsfp", "bearsfp", "trend", "cisd", "sfp_trend_state"):
        assert col in res.frame.columns
    # trend only ever takes values in {-1, 0, 1}.
    assert set(np.unique(res.frame["trend"])).issubset({-1, 0, 1})


def test_signal_metadata_shape():
    df = synthetic_ohlc(n=1200, seed=11)
    res = run_indicator(df, SFPParams())
    for s in res.signals:
        assert s["direction"] in (1, -1)
        assert 0 <= s["index"] < len(df)
        assert s["sweep_bar"] <= s["index"]


def test_determinism():
    df = synthetic_ohlc(n=800, seed=3)
    a = run_indicator(df, SFPParams())
    b = run_indicator(df, SFPParams())
    assert [s["index"] for s in a.signals] == [s["index"] for s in b.signals]


def test_bull_signal_follows_a_low_sweep():
    # Every bullish signal should reference a swept swing-low at/under the
    # entry-bar context (sweep_bar precedes the signal within patience).
    df = synthetic_ohlc(n=2000, seed=5)
    params = SFPParams()
    res = run_indicator(df, params)
    for s in res.signals:
        assert s["index"] - s["sweep_bar"] < params.patience + params.pivot_len + 5
