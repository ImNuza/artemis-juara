"""
yfinance Equity Perp Pre-Listing Backfill

Pulls weekly equity prices for COIN/HOOD/CRCL from yfinance. The HIP-3 splice
in `backtest.load_prices` uses these CSVs only for dates BEFORE each asset's
HL listing date. For post-listing weeks, HL HIP-3 candles are primary
(see `pull_hl_equities.py`).

Output: data/alts/equity_{ASSET}_price.csv with columns ['date', '{ASSET}'].
"""

from __future__ import annotations

import yfinance as yf
import pandas as pd
from pathlib import Path


TICKERS = ["COIN", "CRCL", "HOOD"]
START   = "2022-01-01"
END     = "2026-01-05"  # backfill horizon; HL takes over from each asset's listing date

OUT_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "alts"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for t in TICKERS:
        df = yf.download(t, start=START, end=END, interval="1wk", progress=False)
        if df.empty:
            print(f"{t}: no data returned")
            continue

        close = df["Close"][t] if isinstance(df.columns, pd.MultiIndex) else df["Close"]
        out = close.reset_index()
        out.columns = ["date", t]
        out_path = OUT_DIR / f"equity_{t}_price.csv"
        out.to_csv(out_path, index=False)
        print(f"{t}: {len(out)} weekly bars ({out['date'].min()} -> {out['date'].max()}) -> {out_path}")


if __name__ == "__main__":
    main()
