#!/usr/bin/env python3
"""
straddle_ev.py — Instrument-agnostic expected-value & breakeven engine for a
long-straddle strategy driven by a probabilistic "will-it-move" signal.

Context
-------
You have an ML model that, for a given (instrument, threshold X, horizon N
minutes), predicts whether the instrument will move at least X within the next
N minutes. The model has ~p precision on its positive ("big move") predictions:
when it says "a big move is coming", it is right a fraction p of the time.

You want to monetize that with a LONG STRADDLE (buy ATM call + ATM put, same
strike, same expiry), entered when the model fires and exited ~N minutes later.

The central question this tool answers
--------------------------------------
A long straddle is NOT profitable just because "a move happens". It is profitable
only if the realized move exceeds what you PAID (the total premium, which is set
by implied volatility). Two foundational facts drive everything:

  (1) ATM straddle price  ≈  0.7979 * S * sigma * sqrt(T)          [= sqrt(2/pi)]
  (2) Expected absolute move  E|S_T - S|  ≈  0.7979 * S * sigma * sqrt(T)

i.e. the straddle is priced at roughly the *expected absolute move* implied by
the option's IV. So, mechanically held to expiry:

      EV(straddle)  ≈  E[ |move| ]_realized  −  premium  −  costs
                    ≈  ( realized expected |move|  −  implied expected |move| )  −  costs

Your edge exists only if your signal lifts E[|move| | signal] ABOVE the implied
move embedded in the premium (which itself sits above the *unconditional*
realized move because of the volatility risk premium, IV > RV).

=> Precision alone (p = 0.75) is necessary but NOT sufficient. You also need the
   CONDITIONAL MAGNITUDE distribution of the move given a signal.

This module lets you plug in real numbers (premium from the option chain, or an
IV estimate; your signal's precision; and your conditional move estimates) and
get the EV, breakevens, required edge, and Kelly sizing — for ANY instrument.

Pure standard library (math, random, argparse, dataclasses). No dependencies.

Examples
--------
  # Gold straddle, premium known from the chain ($4.40), signal precision 0.75,
  # conditional mean |move| of $35 on a hit and $8 on a miss, $0.40 round-trip cost:
  python straddle_ev.py ev --premium 4.40 --cost 0.40 -p 0.75 --mu-hit 35 --mu-miss 8

  # Estimate the straddle premium + implied move for gold from IV:
  python straddle_ev.py implied --S 3300 --iv 0.16 --minutes 120 --basis gold24x5

  # Solve: how large must the average |move| on a HIT be to break even?
  python straddle_ev.py required --premium 4.40 --cost 0.40 -p 0.75 --mu-miss 8

  # NASDAQ-100 example with Monte-Carlo conditional distribution:
  python straddle_ev.py mc --premium 95 --cost 6 -p 0.75 \
      --hit-dist lognorm --hit-mean 230 --hit-cv 0.7 --miss-mean 55 --miss-cv 0.6
"""

from __future__ import annotations

import argparse
import math
import random
from dataclasses import dataclass, field
from typing import Callable, Optional

SQRT_2PI = math.sqrt(2.0 * math.pi)
SQRT_2_OVER_PI = math.sqrt(2.0 / math.pi)  # 0.79788456...

# ---------------------------------------------------------------------------
# Time-basis presets: minutes per year used to annualize / de-annualize vol.
# Volatility scales with sqrt(time); the "clock" you use matters for intraday.
#   calendar  -> 24x7 wall-clock (good for ~24h markets if you quote vol that way)
#   equity    -> trading-time, 252 days * 390 min/day (RTH US equities/index)
#   gold24x5  -> ~23h/day * ~252 sessions (COMEX gold is nearly 24x5)
#   fx24x5    -> 24h * 252 sessions
# Pick the basis your IV is quoted in. When in doubt, prefer feeding a real
# premium (the `--premium` path) and skip vol scaling entirely.
# ---------------------------------------------------------------------------
MINUTES_PER_YEAR = {
    "calendar": 365.0 * 24 * 60,        # 525,600
    "equity": 252.0 * 390,              # 98,280  (RTH)
    "equity24": 252.0 * 24 * 60,        # 362,880
    "gold24x5": 252.0 * 23 * 60,        # 347,760
    "fx24x5": 252.0 * 24 * 60,          # 362,880
}


def norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / SQRT_2PI


def years_from_minutes(minutes: float, basis: str = "calendar") -> float:
    mpy = MINUTES_PER_YEAR.get(basis)
    if mpy is None:
        raise ValueError(f"unknown basis '{basis}', choose from {list(MINUTES_PER_YEAR)}")
    return minutes / mpy


# ---------------------------------------------------------------------------
# Black-Scholes (r=q=0 by default; for a 2-hour hold the carry is negligible).
# ---------------------------------------------------------------------------
def bs_price(S: float, K: float, T: float, sigma: float, r: float = 0.0,
             option: str = "call") -> float:
    """European Black-Scholes price. Handles the T->0 / sigma->0 intrinsic limit."""
    if T <= 0 or sigma <= 0:
        intrinsic_call = max(S - K, 0.0)
        intrinsic_put = max(K - S, 0.0)
        return intrinsic_call if option == "call" else intrinsic_put
    vol_t = sigma * math.sqrt(T)
    d1 = (math.log(S / K) + (r + 0.5 * sigma * sigma) * T) / vol_t
    d2 = d1 - vol_t
    disc = math.exp(-r * T)
    if option == "call":
        return S * norm_cdf(d1) - K * disc * norm_cdf(d2)
    return K * disc * norm_cdf(-d2) - S * norm_cdf(-d1)


def atm_straddle_price(S: float, sigma: float, T: float, r: float = 0.0) -> float:
    """Exact ATM (K=S) straddle = call + put, both struck at S."""
    return (bs_price(S, S, T, sigma, r, "call")
            + bs_price(S, S, T, sigma, r, "put"))


def straddle_approx(S: float, sigma: float, T: float) -> float:
    """Brenner-Subrahmanyam: ATM straddle ~ sqrt(2/pi) * S * sigma * sqrt(T)."""
    return SQRT_2_OVER_PI * S * sigma * math.sqrt(T)


def expected_abs_move(S: float, sigma: float, T: float) -> float:
    """E|S_T - S| ~ sqrt(2/pi) * S * sigma * sqrt(T)  (half-normal mean).

    Numerically equal to the ATM-straddle approximation: the straddle is priced
    at the expected absolute move. That identity is the heart of the analysis.
    """
    return SQRT_2_OVER_PI * S * sigma * math.sqrt(T)


def one_sigma_move(S: float, sigma: float, T: float) -> float:
    """The 1-standard-deviation move over the horizon: S * sigma * sqrt(T)."""
    return S * sigma * math.sqrt(T)


# ---------------------------------------------------------------------------
# EV from summary statistics (held-to-expiry baseline).
# ---------------------------------------------------------------------------
@dataclass
class EVResult:
    premium: float
    cost: float
    total_debit: float          # premium + cost = max loss & breakeven distance
    p_hit: float
    mu_hit: float               # E[|move| | signal hit]
    mu_miss: float              # E[|move| | signal miss]
    e_abs_move: float           # blended E[|move| | signal fired]
    ev: float                   # expected P&L per straddle
    ev_per_dollar: float        # EV / total_debit (return on premium risked)
    breakeven_move: float       # |move| needed to break even at expiry
    upper_be: Optional[float] = None
    lower_be: Optional[float] = None

    def report(self) -> str:
        lines = [
            "Long-straddle EV (held to expiry, summary-stat model)",
            "-" * 56,
            f"  premium (debit)        : {self.premium:.4f}",
            f"  round-trip cost        : {self.cost:.4f}",
            f"  total debit (max loss) : {self.total_debit:.4f}",
            f"  breakeven |move|       : {self.breakeven_move:.4f}",
            f"  P(signal is a hit)     : {self.p_hit:.3f}",
            f"  E[|move| | hit]        : {self.mu_hit:.4f}",
            f"  E[|move| | miss]       : {self.mu_miss:.4f}",
            f"  E[|move| | signal]     : {self.e_abs_move:.4f}",
            "-" * 56,
            f"  EXPECTED P&L / straddle: {self.ev:+.4f}",
            f"  EV per $1 risked       : {self.ev_per_dollar:+.3f}",
        ]
        if self.upper_be is not None:
            lines.append(f"  upper/lower breakeven  : {self.upper_be:.2f} / {self.lower_be:.2f}")
        verdict = "POSITIVE edge" if self.ev > 0 else "NEGATIVE edge"
        lines.append(f"  verdict                : {verdict}")
        return "\n".join(lines)


def straddle_ev(premium: float, p_hit: float, mu_hit: float, mu_miss: float,
                cost: float = 0.0, strike: Optional[float] = None) -> EVResult:
    """Expected P&L of buying a straddle when the signal fires.

    Held-to-expiry payoff = |move| - (premium + cost). Taking expectations and
    using E[|move| | signal] = p*mu_hit + (1-p)*mu_miss:

        EV = p*mu_hit + (1-p)*mu_miss - premium - cost
           = E[|move| | signal] - total_debit
    """
    total_debit = premium + cost
    e_abs = p_hit * mu_hit + (1.0 - p_hit) * mu_miss
    ev = e_abs - total_debit
    res = EVResult(
        premium=premium, cost=cost, total_debit=total_debit,
        p_hit=p_hit, mu_hit=mu_hit, mu_miss=mu_miss, e_abs_move=e_abs,
        ev=ev, ev_per_dollar=ev / total_debit if total_debit else float("nan"),
        breakeven_move=total_debit,
    )
    if strike is not None:
        res.upper_be = strike + total_debit
        res.lower_be = strike - total_debit
    return res


def required_mu_hit(premium: float, p_hit: float, mu_miss: float,
                    cost: float = 0.0) -> float:
    """Solve EV=0 for the average |move| on a HIT needed to break even.

        0 = p*mu_hit + (1-p)*mu_miss - (premium+cost)
        mu_hit* = ((premium+cost) - (1-p)*mu_miss) / p
    """
    total_debit = premium + cost
    return (total_debit - (1.0 - p_hit) * mu_miss) / p_hit


# ---------------------------------------------------------------------------
# Monte-Carlo EV from a full conditional distribution of |move|.
# More faithful than summary stats when the hit distribution is fat-tailed
# (which is exactly when straddles pay: the right 25% can carry the strategy).
# ---------------------------------------------------------------------------
def _lognormal_from_mean_cv(mean: float, cv: float, rng: random.Random) -> float:
    """Draw a positive |move| from a lognormal with given mean and coeff. of var."""
    if mean <= 0:
        return 0.0
    sigma2 = math.log(1.0 + cv * cv)
    sigma = math.sqrt(sigma2)
    mu = math.log(mean) - 0.5 * sigma2
    return math.exp(rng.gauss(mu, sigma))


def straddle_ev_mc(premium: float, p_hit: float, cost: float,
                   hit_sampler: Callable[[], float],
                   miss_sampler: Callable[[], float],
                   n: int = 200_000, seed: int = 7) -> dict:
    """Monte-Carlo EV and full P&L distribution (held to expiry).

    Returns EV, std, win rate, percentiles, and the prob of total loss.
    The straddle's convexity (payoff = |move| - debit, floored at -debit) is
    captured exactly by sampling |move| per trade.
    """
    rng = random.Random(seed)
    total_debit = premium + cost
    pnls = []
    wins = 0
    for _ in range(n):
        move = hit_sampler() if rng.random() < p_hit else miss_sampler()
        pnl = move - total_debit          # at expiry; payoff = |move| - debit
        pnls.append(pnl)
        if pnl > 0:
            wins += 1
    pnls.sort()
    mean = sum(pnls) / n
    var = sum((x - mean) ** 2 for x in pnls) / n
    std = math.sqrt(var)

    def pct(q):
        idx = min(n - 1, max(0, int(q * n)))
        return pnls[idx]

    return {
        "ev": mean,
        "std": std,
        "ev_per_dollar": mean / total_debit if total_debit else float("nan"),
        "win_rate": wins / n,
        "p_total_loss": sum(1 for x in pnls if x <= -total_debit + 1e-9) / n,
        "p05": pct(0.05), "p25": pct(0.25), "p50": pct(0.50),
        "p75": pct(0.75), "p95": pct(0.95),
        "min": pnls[0], "max": pnls[-1],
        "total_debit": total_debit, "n": n,
    }


# ---------------------------------------------------------------------------
# Kelly sizing for a non-binary, asymmetric (option) payoff.
# Full Kelly maximizes E[log wealth]; with model uncertainty + fat tails, use a
# fraction (1/4 to 1/2). f* found by maximizing E[log(1 + f * R)] where R is the
# per-trade return on premium risked (R = pnl / total_debit, floored at -1).
# ---------------------------------------------------------------------------
def kelly_fraction(returns: list[float], grid: int = 2000) -> float:
    """Numerically maximize E[log(1 + f R)] over f in [0, 1). R = pnl/debit >= -1."""
    best_f, best_g = 0.0, -float("inf")
    for i in range(1, grid):
        f = i / grid
        ok = True
        s = 0.0
        for r in returns:
            x = 1.0 + f * r
            if x <= 0:
                ok = False
                break
            s += math.log(x)
        if ok and s / len(returns) > best_g:
            best_g, best_f = s / len(returns), f
    return best_f


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _add_common_ev(sp):
    sp.add_argument("--premium", type=float, required=True,
                    help="total straddle premium (debit) in price units")
    sp.add_argument("--cost", type=float, default=0.0,
                    help="round-trip frictions (commissions+slippage), price units")
    sp.add_argument("-p", "--p-hit", type=float, required=True,
                    help="signal precision: P(big move | signal), e.g. 0.75")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    # implied: estimate premium + expected move from IV
    si = sub.add_parser("implied", help="estimate straddle premium & expected move from IV")
    si.add_argument("--S", type=float, required=True, help="underlying price")
    si.add_argument("--iv", type=float, required=True, help="annualized implied vol, e.g. 0.16")
    si.add_argument("--minutes", type=float, required=True, help="horizon in minutes")
    si.add_argument("--basis", default="calendar", choices=list(MINUTES_PER_YEAR))

    # ev: summary-stat EV
    se = sub.add_parser("ev", help="EV from precision + conditional means")
    _add_common_ev(se)
    se.add_argument("--mu-hit", type=float, required=True, help="E[|move| | hit]")
    se.add_argument("--mu-miss", type=float, default=0.0, help="E[|move| | miss]")
    se.add_argument("--strike", type=float, default=None, help="optional strike for breakevens")

    # required: solve for break-even mu_hit
    sr = sub.add_parser("required", help="solve for the mu_hit that makes EV=0")
    _add_common_ev(sr)
    sr.add_argument("--mu-miss", type=float, default=0.0)

    # mc: Monte-Carlo EV from conditional distributions
    sm = sub.add_parser("mc", help="Monte-Carlo EV from conditional |move| distributions")
    _add_common_ev(sm)
    sm.add_argument("--hit-dist", default="lognorm", choices=["lognorm", "fixed"])
    sm.add_argument("--hit-mean", type=float, required=True)
    sm.add_argument("--hit-cv", type=float, default=0.7, help="coeff. of variation of hit |move|")
    sm.add_argument("--miss-mean", type=float, default=0.0)
    sm.add_argument("--miss-cv", type=float, default=0.6)
    sm.add_argument("--n", type=int, default=200_000)
    sm.add_argument("--kelly", action="store_true", help="also report full & 1/4 Kelly sizing")

    args = ap.parse_args(argv)

    if args.cmd == "implied":
        T = years_from_minutes(args.minutes, args.basis)
        prem = atm_straddle_price(args.S, args.iv, T)
        approx = straddle_approx(args.S, args.iv, T)
        em = expected_abs_move(args.S, args.iv, T)
        s1 = one_sigma_move(args.S, args.iv, T)
        print(f"S={args.S}  IV={args.iv:.4f}  horizon={args.minutes:.0f}min  basis={args.basis}")
        print(f"  T (years)              : {T:.6e}")
        print(f"  ATM straddle (exact BS): {prem:.4f}")
        print(f"  ATM straddle (~0.8SsT) : {approx:.4f}")
        print(f"  expected |move| E|dS|  : {em:.4f}")
        print(f"  1-sigma move           : {s1:.4f}")
        print("  note: straddle premium ~ expected |move|; you profit only if the")
        print("        realized move beats this. Compare your threshold X to E|dS|.")
        return

    if args.cmd == "ev":
        res = straddle_ev(args.premium, args.p_hit, args.mu_hit, args.mu_miss,
                          cost=args.cost, strike=args.strike)
        print(res.report())
        req = required_mu_hit(args.premium, args.p_hit, args.mu_miss, args.cost)
        print(f"  (break-even needs E[|move| | hit] >= {req:.4f})")
        return

    if args.cmd == "required":
        req = required_mu_hit(args.premium, args.p_hit, args.mu_miss, args.cost)
        print(f"To break even at p={args.p_hit:.3f}, mu_miss={args.mu_miss:.3f}, "
              f"debit={args.premium+args.cost:.3f}:")
        print(f"  required E[|move| | hit] >= {req:.4f}")
        print("  Ask your ML team for the realized |move| distribution on positive")
        print("  signals and check its mean clears this bar with margin.")
        return

    if args.cmd == "mc":
        rng = random.Random(12345)
        if args.hit_dist == "fixed":
            hit = lambda: args.hit_mean
        else:
            hit = lambda: _lognormal_from_mean_cv(args.hit_mean, args.hit_cv, rng)
        miss = lambda: _lognormal_from_mean_cv(args.miss_mean, args.miss_cv, rng) \
            if args.miss_mean > 0 else 0.0
        out = straddle_ev_mc(args.premium, args.p_hit, args.cost, hit, miss, n=args.n)
        print("Long-straddle EV (Monte-Carlo, held to expiry)")
        print("-" * 56)
        print(f"  EXPECTED P&L / straddle: {out['ev']:+.4f}   (std {out['std']:.3f})")
        print(f"  EV per $1 risked       : {out['ev_per_dollar']:+.3f}")
        print(f"  P&L win rate           : {out['win_rate']:.3f}")
        print(f"  prob of ~total loss    : {out['p_total_loss']:.3f}")
        print(f"  P&L pctiles 5/25/50/75/95: "
              f"{out['p05']:+.2f} / {out['p25']:+.2f} / {out['p50']:+.2f} / "
              f"{out['p75']:+.2f} / {out['p95']:+.2f}")
        print(f"  worst / best           : {out['min']:+.2f} / {out['max']:+.2f}")
        if args.kelly:
            rng2 = random.Random(999)
            hit2 = (lambda: args.hit_mean) if args.hit_dist == "fixed" \
                else (lambda: _lognormal_from_mean_cv(args.hit_mean, args.hit_cv, rng2))
            miss2 = (lambda: _lognormal_from_mean_cv(args.miss_mean, args.miss_cv, rng2)) \
                if args.miss_mean > 0 else (lambda: 0.0)
            debit = args.premium + args.cost
            rets = []
            for _ in range(20000):
                mv = hit2() if rng2.random() < args.p_hit else miss2()
                rets.append((mv - debit) / debit)
            f = kelly_fraction(rets)
            print("-" * 56)
            print(f"  full-Kelly fraction    : {f:.3f} of bankroll per trade")
            print(f"  1/4-Kelly (recommended): {f/4:.3f}")
            print("  (use fractional Kelly; full Kelly is too aggressive under model")
            print("   uncertainty and fat tails)")
        return


if __name__ == "__main__":
    main()
