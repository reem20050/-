#!/usr/bin/env python3
"""
optimize_threshold_horizon.py — Optuna search over the straddle strategy's
(threshold X, horizon N), built to RESIST backtest overfitting.

Why this file is shaped the way it is
-------------------------------------
Two non-negotiable principles, both learned the hard way (see ../03, ../04, ../07,
../08):

  1. OPTIMIZE NET P&L, NOT PRECISION. A 75%-precision threshold can be deeply
     unprofitable (precision != win-rate != EV). The Optuna objective here is the
     OUT-OF-SAMPLE risk-adjusted NET P&L of the straddle trades, after costs.

  2. OPTUNA OVER (X, N) IS MULTIPLE TESTING. Searching hundreds of (X, N) combos
     and keeping the best Sharpe *guarantees* an inflated, overfit result. This
     harness defends against that with, at every layer:
        - walk-forward / purged-embargoed evaluation INSIDE each trial
        - threshold parameterized in SIGMA-UNITS (X = k * implied_move(N)), which
          decouples X from the known X ~ sqrt(N) scaling and stabilizes the search
        - Deflated Sharpe Ratio (Bailey & Lopez de Prado) on the winner, given the
          number of trials actually run
        - a PLATEAU check: the optimum must be surrounded by good neighbors, not a
          lone spike
        - a FINAL HOLDOUT that Optuna never sees

What YOU must plug in (two functions, clearly marked `# === PLUG IN ===`)
------------------------------------------------------------------------
  A. predicted_move(df, horizon_min)  -> per-bar model output (predicted |move|
     over the next horizon_min). Use YOUR model. If your model must be retrained
     per (X, N), do it here and cache; if it outputs a magnitude/quantile, no
     retrain is needed (recommended — see ../04 meta-labeling / magnitude head).

  B. straddle_pnl(entry_ts, horizon_min, ctx) -> net P&L of one straddle, from
     REAL option quotes (buy at ASK, sell at BID, minus commissions). Modeled IV
     is only a fallback for wiring up the pipeline — NOT for real decisions
     (you correctly pointed out we don't know the real theta/gamma/premium).

Run the self-contained synthetic demo (clearly fake data) to see the mechanics:
    pip install optuna numpy pandas
    python optimize_threshold_horizon.py --demo --trials 60
"""

from __future__ import annotations

import argparse
import math
from dataclasses import dataclass, field
from statistics import NormalDist
from typing import Callable, Optional

import numpy as np

try:
    import pandas as pd
except ImportError:  # pandas only needed for the data plumbing
    pd = None

# Reuse the validated identity engine for implied-move / premium estimates.
from straddle_ev import one_sigma_move, expected_abs_move, years_from_minutes

_NORM = NormalDist()
_EULER = 0.5772156649015329


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
@dataclass
class SearchConfig:
    # search space
    horizon_grid: tuple = (30, 45, 60, 90, 120, 180, 240, 300)  # minutes (N)
    k_low: float = 0.6          # threshold in sigma-units: X = k * implied_move(N)
    k_high: float = 3.0
    # evaluation
    n_folds: int = 5            # walk-forward folds
    embargo_frac: float = 0.01  # gap between train and test (fraction of span)
    min_trades: int = 30        # a fold/param with fewer OOS trades is penalized
    # market / costs (used by the MODELED fallback only; real quotes override)
    vol_basis: str = "equity"
    cost_frac_of_premium: float = 0.06   # round-trip friction as frac of premium
    cost_fixed: float = 0.0              # fixed cost per trade (price units)
    # objective
    objective: str = "sharpe"   # "sharpe" | "net_ev" | "calmar"
    seed: int = 7


# ---------------------------------------------------------------------------
# === PLUG IN (A): your model's predicted move magnitude per bar ===
# ---------------------------------------------------------------------------
def predicted_move(df, horizon_min: int) -> "pd.Series":
    """Return predicted |move| over the next `horizon_min`, indexed like df.

    REPLACE THIS with your model. Contract:
      - one value per bar (the model's forecast of the absolute move over the
        next `horizon_min` minutes, in price units), OR a monotone score.
      - must use ONLY information available at/before the bar (no leakage).
      - if your model is a binary classifier retrained per (X, horizon), wrap the
        retrain here and return the decision score; but a magnitude/quantile head
        (../04) lets you avoid retraining for every X.
    """
    raise NotImplementedError("Plug in your model's predicted_move(df, horizon_min).")


# ---------------------------------------------------------------------------
# === PLUG IN (B): net P&L of one straddle from REAL quotes ===
# ---------------------------------------------------------------------------
def straddle_pnl_from_quotes(entry_ts, horizon_min: int, ctx: dict) -> Optional[float]:
    """Net P&L (price units) of one ATM straddle entered at entry_ts, exited
    `horizon_min` later, from REAL option quotes.

    REPLACE THIS. Correct implementation:
        buy_debit  = call_ask(entry_ts) + put_ask(entry_ts)      # cross the spread
        sell_credit= call_bid(exit_ts)  + put_bid(exit_ts)       # cross again
        return sell_credit - buy_debit - commissions
    Return None to skip (stale/locked quote, no market). This is the ONLY way to
    capture the real theta/gamma/IV-crush/spread — modeled IV cannot.
    """
    raise NotImplementedError("Plug in straddle_pnl_from_quotes against your option data.")


def straddle_pnl_modeled(realized_move: float, S: float, iv: float,
                         horizon_min: int, cfg: SearchConfig) -> float:
    """FALLBACK ONLY (wiring/demo). At-expiry approximation:
        premium ~= E|move|(N)  (the identity straddle ~= expected move)
        pnl ~= realized_move - premium - costs
    Flagged everywhere as an estimate; NOT valid for real sizing/decisions.
    """
    T = years_from_minutes(horizon_min, cfg.vol_basis)
    premium = expected_abs_move(S, iv, T)
    costs = cfg.cost_frac_of_premium * premium + cfg.cost_fixed
    return realized_move - premium - costs


# ---------------------------------------------------------------------------
# Walk-forward splitter with embargo (prevents train/test leakage on time series)
# ---------------------------------------------------------------------------
def walk_forward_folds(n: int, n_folds: int, embargo: int):
    """Yield (train_idx, test_idx) for expanding-window walk-forward.
    `embargo` rows are dropped between train end and test start."""
    fold = n // (n_folds + 1)
    for i in range(1, n_folds + 1):
        train_end = fold * i
        test_start = min(n, train_end + embargo)
        test_end = min(n, train_end + fold)
        if test_start >= test_end:
            continue
        yield np.arange(0, train_end), np.arange(test_start, test_end)


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------
def _annualization(timestamps) -> float:
    """trades-per-year implied by the spacing of trade entry times."""
    if pd is None or len(timestamps) < 2:
        return 252.0
    span_days = (timestamps[-1] - timestamps[0]) / np.timedelta64(1, "D")
    if span_days <= 0:
        return 252.0
    return max(1.0, len(timestamps) / span_days * 252.0)


def trade_metrics(pnls: np.ndarray, premiums: np.ndarray, timestamps) -> dict:
    if len(pnls) == 0:
        return {"n": 0, "net_ev": 0.0, "sharpe": 0.0, "sharpe_raw": 0.0,
                "calmar": 0.0, "win_rate": 0.0, "rets": np.array([])}
    rets = pnls / np.where(premiums > 0, premiums, np.nan)        # return on premium risked
    rets = rets[~np.isnan(rets)]
    mu = rets.mean()
    sd = rets.std(ddof=1) if len(rets) > 1 else 0.0
    sharpe_raw = (mu / sd) if sd > 0 else 0.0                      # per-trade (for DSR)
    sharpe = sharpe_raw * math.sqrt(_annualization(timestamps))    # annualized (for objective)
    equity = np.cumsum(pnls)
    peak = np.maximum.accumulate(equity)
    max_dd = float(np.max(peak - equity)) if len(equity) else 0.0
    calmar = (pnls.sum() / max_dd) if max_dd > 0 else 0.0
    return {"n": len(pnls), "net_ev": float(pnls.mean()), "sharpe": float(sharpe),
            "sharpe_raw": float(sharpe_raw), "calmar": float(calmar),
            "win_rate": float((pnls > 0).mean()), "rets": rets}


# ---------------------------------------------------------------------------
# One (X, N) evaluation over walk-forward OOS folds
# ---------------------------------------------------------------------------
def evaluate_params(df, k: float, horizon_min: int, cfg: SearchConfig,
                    pnl_fn: Callable, report=None) -> dict:
    """Generate signals at threshold X=k*implied_move(N), backtest the straddle on
    each walk-forward TEST fold, aggregate OOS metrics. `report(step, value)` is an
    optional pruning hook (per fold)."""
    n = len(df)
    embargo = max(1, int(cfg.embargo_frac * n))
    pred = predicted_move(df, horizon_min).to_numpy()
    S = df["S"].to_numpy()
    iv = df["iv"].to_numpy()
    fwd_move = df[f"fwd_move_{horizon_min}"].to_numpy()    # realized |move| over N (precomputed)
    ts = df.index.to_numpy()

    all_pnl, all_prem, all_ts = [], [], []
    for step, (tr, te) in enumerate(walk_forward_folds(n, cfg.n_folds, embargo)):
        # threshold X per bar, in sigma units (decoupled from sqrt(N) scaling)
        thr = k * one_sigma_move(S[te], iv[te], years_from_minutes(horizon_min, cfg.vol_basis))
        fire = pred[te] >= thr
        idx = te[fire]
        pnls, prems = [], []
        for j in idx:
            prem = expected_abs_move(S[j], iv[j], years_from_minutes(horizon_min, cfg.vol_basis))
            p = pnl_fn(ts[j], horizon_min,
                       {"S": S[j], "iv": iv[j], "realized_move": fwd_move[j], "cfg": cfg})
            if p is None:
                continue
            pnls.append(p); prems.append(prem)
        m = trade_metrics(np.array(pnls), np.array(prems), ts[idx[:len(pnls)]])
        all_pnl += pnls; all_prem += prems; all_ts += list(ts[idx[:len(pnls)]])
        if report is not None:
            report(step, m["sharpe"])           # enables Optuna pruning

    m = trade_metrics(np.array(all_pnl), np.array(all_prem), np.array(all_ts))
    # penalize too-few trades (unstable / overfit-prone)
    if m["n"] < cfg.min_trades:
        m["sharpe"] *= m["n"] / cfg.min_trades
        m["net_ev"] *= m["n"] / cfg.min_trades
    return m


def _objective_value(m: dict, cfg: SearchConfig) -> float:
    return {"sharpe": m["sharpe"], "net_ev": m["net_ev"], "calmar": m["calmar"]}[cfg.objective]


# ---------------------------------------------------------------------------
# Deflated Sharpe Ratio — penalize for the number of Optuna trials
# ---------------------------------------------------------------------------
def deflated_sharpe(best_rets: np.ndarray, trial_sharpes: list, n_trials: int) -> float:
    """Probability the best Sharpe is real given n_trials were tried (Bailey & Lopez
    de Prado 2014). Uses the winner's per-trade return distribution (skew/kurt) and
    the variance of Sharpe across trials for the expected-max-Sharpe benchmark."""
    if len(best_rets) < 3:
        return float("nan")
    T = len(best_rets)
    sr = best_rets.mean() / best_rets.std(ddof=1) if best_rets.std(ddof=1) > 0 else 0.0
    # higher moments of returns
    g3 = float(((best_rets - best_rets.mean()) ** 3).mean() / (best_rets.std() ** 3 + 1e-12))
    g4 = float(((best_rets - best_rets.mean()) ** 4).mean() / (best_rets.std() ** 4 + 1e-12))
    # expected maximum Sharpe under the null (SR0)
    v = np.var(trial_sharpes, ddof=1) if len(trial_sharpes) > 1 else 0.0
    Nt = max(2, n_trials)
    sr0 = math.sqrt(v) * ((1 - _EULER) * _NORM.inv_cdf(1 - 1.0 / Nt)
                          + _EULER * _NORM.inv_cdf(1 - 1.0 / (Nt * math.e)))
    denom = math.sqrt(max(1e-12, 1 - g3 * sr + (g4 - 1) / 4.0 * sr * sr))
    dsr = _NORM.cdf((sr - sr0) * math.sqrt(T - 1) / denom)
    return float(dsr)


# ---------------------------------------------------------------------------
# Optuna driver
# ---------------------------------------------------------------------------
def run_study(df, cfg: SearchConfig, n_trials: int, pnl_fn: Callable):
    try:
        import optuna
        from optuna.samplers import TPESampler
        from optuna.pruners import MedianPruner
    except ImportError:
        raise SystemExit("Optuna required:  pip install optuna numpy pandas")
    optuna.logging.set_verbosity(optuna.logging.WARNING)

    trial_sharpes: list = []

    def objective(trial):
        N = trial.suggest_categorical("horizon_min", list(cfg.horizon_grid))
        k = trial.suggest_float("threshold_sigma", cfg.k_low, cfg.k_high)

        def report(step, value):
            trial.report(value, step)
            if trial.should_prune():
                raise optuna.TrialPruned()

        m = evaluate_params(df, k, N, cfg, pnl_fn, report=report)
        trial.set_user_attr("n_trades", m["n"])
        trial.set_user_attr("net_ev", m["net_ev"])
        trial.set_user_attr("win_rate", m["win_rate"])
        trial_sharpes.append(m["sharpe_raw"])   # per-trade units, for the DSR benchmark
        return _objective_value(m, cfg)          # annualized objective for Optuna

    study = optuna.create_study(direction="maximize",
                                sampler=TPESampler(seed=cfg.seed, multivariate=True),
                                pruner=MedianPruner(n_warmup_steps=1))
    study.optimize(objective, n_trials=n_trials)
    return study, trial_sharpes


def plateau_check(df, cfg: SearchConfig, best_params: dict, pnl_fn: Callable) -> dict:
    """A trustworthy optimum is surrounded by good neighbors, not a lone spike.
    Re-evaluate +/- one step in N and +/-0.2 in k; report the worst neighbor."""
    grid = list(cfg.horizon_grid)
    N = best_params["horizon_min"]; k = best_params["threshold_sigma"]
    i = grid.index(N)
    neigh_N = [grid[max(0, i - 1)], grid[min(len(grid) - 1, i + 1)]]
    neigh_k = [max(cfg.k_low, k - 0.2), min(cfg.k_high, k + 0.2)]
    vals = []
    for nn in set(neigh_N):
        for kk in set(neigh_k):
            vals.append(_objective_value(evaluate_params(df, kk, nn, cfg, pnl_fn), cfg))
    return {"neighbors_min": float(min(vals)), "neighbors_mean": float(np.mean(vals))}


# ---------------------------------------------------------------------------
# Synthetic demo data (CLEARLY FAKE — for wiring only)
# ---------------------------------------------------------------------------
def make_demo(cfg: SearchConfig, n_bars=8000):
    if pd is None:
        raise SystemExit("pandas required for the demo:  pip install pandas")
    rng = np.random.default_rng(cfg.seed)
    idx = pd.date_range("2025-01-01 09:30", periods=n_bars, freq="5min")
    iv = np.clip(0.22 + 0.03 * np.sin(np.arange(n_bars) / 300) + rng.normal(0, 0.01, n_bars), 0.1, 0.6)
    # generate the price path AT the stated IV so realized vol ~= implied vol
    # (otherwise the straddle is mispriced by construction and nothing ever fires).
    dt = years_from_minutes(5, cfg.vol_basis)
    rets = iv * math.sqrt(dt) * rng.standard_normal(n_bars)
    S = 30000.0 * np.exp(np.cumsum(rets))
    df = pd.DataFrame({"S": S, "iv": iv}, index=idx)
    # precompute realized forward |move| for each candidate horizon (bars of 5 min)
    for N in cfg.horizon_grid:
        h = max(1, N // 5)
        df[f"fwd_move_{N}"] = (df["S"].shift(-h) - df["S"]).abs()
    # SYNTHETIC "model": a skilled-but-noisy forecast of the 60-min forward |move|
    base = df["fwd_move_60"].to_numpy()
    noise = rng.normal(0.0, np.nanstd(base) * 0.8, n_bars)
    df["_pred"] = np.clip(0.6 * base + noise, 0.0, None)
    df = df.dropna()
    return df


def _demo_predicted_move(df, horizon_min):
    # scale the single synthetic score across horizons by sqrt(N/60)
    return df["_pred"] * math.sqrt(horizon_min / 60.0)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--demo", action="store_true", help="run on synthetic fake data")
    ap.add_argument("--trials", type=int, default=60)
    ap.add_argument("--objective", default="sharpe", choices=["sharpe", "net_ev", "calmar"])
    ap.add_argument("--holdout-frac", type=float, default=0.2,
                    help="final untouched test fraction (chronological tail)")
    args = ap.parse_args(argv)

    cfg = SearchConfig(objective=args.objective)

    if not args.demo:
        raise SystemExit(
            "Plug in predicted_move() and straddle_pnl_from_quotes() against your\n"
            "real signals + option quotes, load your DataFrame (columns: S, iv,\n"
            "fwd_move_<N> for each horizon), then call run_study(). Use --demo to\n"
            "see the mechanics on synthetic data first.")

    # --- DEMO wiring ---
    global predicted_move
    predicted_move = _demo_predicted_move
    pnl_fn = lambda ts, N, ctx: straddle_pnl_modeled(
        ctx["realized_move"], ctx["S"], ctx["iv"], N, ctx["cfg"])

    df = make_demo(cfg)
    cut = int(len(df) * (1 - args.holdout_frac))
    df_opt, df_hold = df.iloc[:cut], df.iloc[cut:]      # holdout Optuna never sees

    print(f"[demo] SYNTHETIC DATA — not real. bars={len(df)}  "
          f"opt={len(df_opt)} holdout={len(df_hold)}  objective={cfg.objective}")
    study, trial_sharpes = run_study(df_opt, cfg, args.trials, pnl_fn)
    bp = study.best_params
    print(f"\nBEST (in-sample/OOS-folds): {bp}  value={study.best_value:.3f}")

    # overfitting defenses on the winner
    plat = plateau_check(df_opt, cfg, bp, pnl_fn)
    m_hold = evaluate_params(df_hold, bp["threshold_sigma"], bp["horizon_min"], cfg, pnl_fn)
    dsr = deflated_sharpe(m_hold["rets"], trial_sharpes, len(trial_sharpes))

    print("\n--- overfitting checks (the part that matters) ---")
    print(f"  plateau: best={study.best_value:.3f}  worst-neighbor={plat['neighbors_min']:.3f}  "
          f"mean-neighbor={plat['neighbors_mean']:.3f}")
    print(f"    -> trust it only if the worst neighbor is still good (no lone spike)")
    print(f"  HOLDOUT (untouched): n={m_hold['n']}  net_ev={m_hold['net_ev']:.3f}  "
          f"sharpe={m_hold['sharpe']:.3f}  win_rate={m_hold['win_rate']:.2f}")
    print(f"  Deflated Sharpe (vs {len(trial_sharpes)} trials): {dsr:.3f}  "
          f"(>0.95 = likely real; <0.9 = probably overfit noise)")
    print("\nNOTE: demo P&L is MODELED (premium = E|move|). For real decisions plug in\n"
          "      straddle_pnl_from_quotes() with actual bid/ask — see the docstring.")


if __name__ == "__main__":
    main()
