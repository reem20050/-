import numpy as np
import pandas as pd

from sfp import (
    SFPParams, run_indicator, synthetic_ohlc,
    BacktestConfig, run_backtest, compute_metrics,
)


def _run(seed=7, bars=2000, **cfg_kwargs):
    df = synthetic_ohlc(n=bars, seed=seed)
    res = run_indicator(df, SFPParams())
    bt = run_backtest(res, BacktestConfig(**cfg_kwargs))
    return res, bt


def test_backtest_runs_and_sizes_risk():
    res, bt = _run(rr=2.0)
    assert bt.n_trades > 0
    tr = bt.trades
    # Risk is always positive (stop on the correct side of entry).
    assert (tr["risk_per_unit"] > 0).all()
    # Losses cluster near -1R; rr targets near +2R (allow small fee/rounding).
    losers = tr.loc[tr["exit_reason"] == "stop", "R"]
    if len(losers):
        assert np.allclose(losers, -1.0, atol=0.05)
    winners = tr.loc[tr["exit_reason"] == "target", "R"]
    if len(winners):
        assert np.allclose(winners, 2.0, atol=0.05)


def test_no_overlapping_trades():
    _, bt = _run()
    tr = bt.trades.sort_values("entry_bar").reset_index(drop=True)
    for i in range(1, len(tr)):
        assert tr.loc[i, "entry_bar"] > tr.loc[i - 1, "exit_bar"]


def test_metrics_keys_present():
    _, bt = _run()
    m = compute_metrics(bt)
    for key in ("n_trades", "win_rate", "expectancy_R", "profit_factor",
                "total_return_pct", "max_drawdown_pct", "final_equity"):
        assert key in m
    assert 0.0 <= m["win_rate"] <= 1.0
    assert m["max_drawdown_pct"] >= 0.0


def test_fees_reduce_expectancy():
    _, bt_nofee = _run(fee_pct=0.0)
    _, bt_fee = _run(fee_pct=0.1)
    m0 = compute_metrics(bt_nofee)
    m1 = compute_metrics(bt_fee)
    assert m1["expectancy_R"] <= m0["expectancy_R"] + 1e-9


def test_empty_signals_metrics_safe():
    # A flat, structureless series should produce few/no signals without error.
    n = 300
    idx = pd.bdate_range("2020-01-01", periods=n)
    flat = pd.DataFrame(
        {"open": 100.0, "high": 100.5, "low": 99.5, "close": 100.0}, index=idx
    )
    res = run_indicator(flat, SFPParams())
    bt = run_backtest(res, BacktestConfig())
    m = compute_metrics(bt)
    assert m["n_trades"] == bt.n_trades
