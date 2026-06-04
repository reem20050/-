#!/usr/bin/env python3
"""Parameter sweep over the SFP system; prints the top configurations.

Example
-------
    python scripts/param_sweep.py --source synthetic --bars 3000 --top 15
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd  # noqa: E402

from sfp import synthetic_ohlc, load_csv, load_yfinance  # noqa: E402
from sfp import SFPParams, BacktestConfig, grid_search  # noqa: E402


def main(argv=None):
    p = argparse.ArgumentParser(description="SFP parameter sweep")
    p.add_argument("--source", choices=["synthetic", "csv", "yfinance"],
                   default="synthetic")
    p.add_argument("--csv")
    p.add_argument("--ticker", default="AAPL")
    p.add_argument("--period", default="5y")
    p.add_argument("--bars", type=int, default=3000)
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--top", type=int, default=15)
    p.add_argument("--out-csv", help="dump full sweep results to CSV")
    args = p.parse_args(argv)

    if args.source == "synthetic":
        df = synthetic_ohlc(n=args.bars, seed=args.seed)
    elif args.source == "csv":
        df = load_csv(args.csv)
    else:
        df = load_yfinance(args.ticker, period=args.period)

    # A deliberately modest grid: indicator structure x trade management.
    grid = {
        "pivot_len": [8, 12, 16],
        "patience": [5, 7, 10],
        "tolerance": [0.5, 0.7, 0.9],
        "rr": [1.5, 2.0, 3.0],
    }
    results = grid_search(
        df, grid,
        base_indicator=SFPParams(),
        base_config=BacktestConfig(stop_mode="sweep", target_mode="rr"),
    )

    pd.set_option("display.width", 200)
    pd.set_option("display.max_columns", 30)
    cols = ["pivot_len", "patience", "tolerance", "rr", "score", "n_trades",
            "win_rate", "expectancy_R", "profit_factor", "total_return_pct",
            "max_drawdown_pct"]
    cols = [c for c in cols if c in results.columns]
    print(f"\nSweep over {len(results)} configurations "
          f"({args.source}, bars={len(df)}). Top {args.top} by score:\n")
    print(results[cols].head(args.top).to_string(index=False))

    if args.out_csv:
        results.to_csv(args.out_csv, index=False)
        print(f"\nFull results -> {args.out_csv}")


if __name__ == "__main__":
    main()
