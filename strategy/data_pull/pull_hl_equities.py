"""
Hyperliquid HIP-3 Equity Perp Pull

Pulls daily candles from the HIP-3 perp dex `xyz` for COIN/HOOD/CRCL and
resamples to weekly Friday close. yfinance still provides the pre-listing
backfill (handled in backtest.load_prices); this script provides the
post-listing leg of the splice so HL is the venue-correct fill reference
for any period during which the asset was actually listed on HL.

Output: data/alts/equity_{ASSET}_hl.csv with columns ['date', '{ASSET}'].
"""

from __future__ import annotations

import time
import requests
import pandas as pd
from datetime import datetime, timezone
from pathlib import Path


HL_URL = "https://api.hyperliquid.xyz/info"

# HIP-3 listing dates verified via candleSnapshot 2026-05-07.
# Backed by project_hip3_splice_pending.md memory.
LISTINGS = {
    "COIN": "2025-11-25",
    "HOOD": "2025-11-26",
    "CRCL": "2025-12-15",
}

OUT_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "alts"


def hl_post(payload: dict, retries: int = 3) -> list:
    last: Exception | None = None
    for attempt in range(retries):
        try:
            r = requests.post(HL_URL, headers={"Content-Type": "application/json"},
                              json=payload, timeout=20)
            r.raise_for_status()
            return r.json()
        except Exception as exc:
            last = exc
            time.sleep(1.5)
    raise RuntimeError(f"HL request failed after {retries} attempts: {last}")


def fetch_weekly(coin: str, start: str) -> pd.DataFrame:
    """Fetch HL daily candles for `coin` from `start` to now; resample to W-FRI."""
    end = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    start_ms = int(datetime.strptime(start, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp() * 1000)
    end_ms   = int(datetime.strptime(end,   "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp() * 1000)

    candles = hl_post({
        "type": "candleSnapshot",
        "req": {"coin": coin, "interval": "1d",
                "startTime": start_ms, "endTime": end_ms},
    })
    if not candles:
        return pd.DataFrame(columns=["date", coin.replace("xyz:", "")])

    df = pd.DataFrame(candles)
    df["date"]  = pd.to_datetime(df["t"].astype(int), unit="ms", utc=True).dt.tz_localize(None).dt.normalize()
    df["close"] = df["c"].astype(float)
    df = df[["date", "close"]].drop_duplicates("date").set_index("date").sort_index()
    weekly = df["close"].resample("W-FRI").last().dropna()
    asset = coin.replace("xyz:", "")
    out = weekly.reset_index()
    out.columns = ["date", asset]
    return out


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for asset, listing in LISTINGS.items():
        print(f"\n{asset}: HL HIP-3 perp xyz:{asset} from {listing}...")
        df = fetch_weekly(f"xyz:{asset}", listing)
        if df.empty:
            print(f"  WARNING: no candles returned for xyz:{asset}")
            continue
        out_path = OUT_DIR / f"equity_{asset}_hl.csv"
        df.to_csv(out_path, index=False)
        print(f"  Saved: {out_path} ({len(df)} weekly bars, {df['date'].min()} -> {df['date'].max()})")


if __name__ == "__main__":
    main()
