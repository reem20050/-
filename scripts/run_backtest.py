#!/usr/bin/env python3
"""Run the SFP indicator + backtest on a dataset and print metrics.

Examples
--------
    # Synthetic data (works offline, in the sandbox):
    python scripts/run_backtest.py --source synthetic --bars 2000 --plot

    # Your own CSV (columns: date/open/high/low/close):
    python scripts/run_backtest.py --source csv --csv data/BTCUSD_1h.csv --rr 2

    # yfinance (only where Yahoo is reachable, e.g. your laptop):
    python scripts/run_backtest.py --source yfinance --ticker AAPL --period 5y
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sfp import (  # noqa: E402
    SFPParams, run_indicator, BacktestConfig, run_backtest,
    compute_metrics, format_metrics, synthetic_ohlc, load_csv, load_yfinance,
)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="SFP backtest runner")
    src = p.add_argument_group("data source")
    src.add_argument("--source", choices=["synthetic", "csv", "yfinance"],
                     default="synthetic")
    src.add_argument("--csv", help="path to OHLC csv (for --source csv)")
    src.add_argument("--ticker", default="AAPL")
    src.add_argument("--period", default="2y")
    src.add_argument("--interval", default="1d")
    src.add_argument("--bars", type=int, default=2000, help="synthetic bar count")
    src.add_argument("--seed", type=int, default=7, help="synthetic seed")

    ind = p.add_argument_group("indicator")
    ind.add_argument("--pivot-len", type=int, default=12)
    ind.add_argument("--max-edge", type=int, default=50)
    ind.add_argument("--patience", type=int, default=7)
    ind.add_argument("--tolerance", type=float, default=0.7)

    bt = p.add_argument_group("backtest")
    bt.add_argument("--entry", choices=["next_open", "close"], default="next_open")
    bt.add_argument("--stop-mode", choices=["sweep", "atr", "pct"], default="sweep")
    bt.add_argument("--stop-buffer-pct", type=float, default=0.05)
    bt.add_argument("--atr-mult", type=float, default=1.5)
    bt.add_argument("--stop-pct", type=float, default=1.0)
    bt.add_argument("--target-mode", choices=["rr", "opposite", "none"], default="rr")
    bt.add_argument("--rr", type=float, default=2.0)
    bt.add_argument("--max-hold-bars", type=int, default=0)
    bt.add_argument("--no-exit-opposite", action="store_true")
    bt.add_argument("--fee-pct", type=float, default=0.0)
    bt.add_argument("--risk-frac", type=float, default=0.01)

    out = p.add_argument_group("output")
    out.add_argument("--plot", action="store_true", help="write PNG charts")
    out.add_argument("--out-dir", default="out")
    out.add_argument("--trades-csv", help="optional path to dump the trade blotter")
    return p


def load_data(args):
    if args.source == "synthetic":
        return synthetic_ohlc(n=args.bars, seed=args.seed)
    if args.source == "csv":
        if not args.csv:
            raise SystemExit("--csv is required when --source csv")
        return load_csv(args.csv)
    return load_yfinance(args.ticker, period=args.period, interval=args.interval)


def main(argv=None):
    args = build_parser().parse_args(argv)
    df = load_data(args)

    params = SFPParams(
        pivot_len=args.pivot_len, max_edge=args.max_edge,
        patience=args.patience, tolerance=args.tolerance,
    )
    result = run_indicator(df, params)

    cfg = BacktestConfig(
        entry=args.entry, stop_mode=args.stop_mode,
        stop_buffer_pct=args.stop_buffer_pct, atr_mult=args.atr_mult,
        stop_pct=args.stop_pct, target_mode=args.target_mode, rr=args.rr,
        max_hold_bars=args.max_hold_bars,
        exit_on_opposite=not args.no_exit_opposite,
        fee_pct=args.fee_pct, risk_frac=args.risk_frac,
    )
    bt = run_backtest(result, cfg)
    metrics = compute_metrics(bt)

    print(f"\nData: {args.source}  bars={len(df)}  "
          f"signals={len(result.signals)}  trades={bt.n_trades}")
    print("-" * 52)
    print(format_metrics(metrics))

    if args.trades_csv:
        bt.trades.to_csv(args.trades_csv, index=False)
        print(f"\nTrade blotter -> {args.trades_csv}")

    if args.plot:
        from sfp.plotting import plot_signals, plot_equity
        os.makedirs(args.out_dir, exist_ok=True)
        sp = plot_signals(result, os.path.join(args.out_dir, "signals.png"))
        ep = plot_equity(bt, os.path.join(args.out_dir, "equity.png"))
        print(f"\nCharts -> {sp}\n         {ep}")


if __name__ == "__main__":
    main()
