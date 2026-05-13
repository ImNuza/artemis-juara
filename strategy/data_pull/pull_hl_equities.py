"""
Hyperliquid HIP-3 Equity Perp Pull — Prices + Funding Rates

Pulls daily candles AND funding history from the HIP-3 perp dex `xyz`
for COIN/HOOD/CRCL. Both are resampled to weekly Friday.

Prices: yfinance provides pre-listing backfill (handled in backtest.load_prices);
this script provides the post-listing leg of the splice so HL is the venue-correct
fill reference for any period during which the asset was actually listed on HL.

Funding: only available from each asset's HIP-3 listing date forward. Pre-listing
weeks get neutral-50 in the backtest (no signal, no penalty). No Bybit/CEX backfill
for equity funding — the perps only exist on HL.

Outputs:
  data/alts/equity_{ASSET}_hl.csv         — weekly prices
  data/alts/equity_funding_hl.csv         — weekly funding rates (all 3 assets)
"""

from __future__ import annotations

import time
import requests
import pandas as pd
from datetime import datetime, timezone, timedelta
from pathlib import Path


HL_URL = "https://api.hyperliquid.xyz/info"

# HIP-3 listing dates verified via candleSnapshot 2026-05-07.
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


def _last_friday() -> str:
    today = datetime.now(timezone.utc).date()
    fri = today - timedelta(days=(today.weekday() - 4) % 7)
    return fri.strftime("%Y-%m-%d")


def fetch_weekly_prices(coin: str, start: str) -> pd.DataFrame:
    """Fetch HL daily candles for `coin` from `start` to last complete Friday; resample to W-FRI."""
    end = _last_friday()
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


def fetch_weekly_funding(coin: str, start: str) -> pd.Series:
    """Fetch HL funding history for `coin`, paginate by 20-day windows, resample to W-FRI sum."""
    end = _last_friday()
    start_dt = datetime.strptime(start, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    end_dt   = datetime.strptime(end,   "%Y-%m-%d").replace(tzinfo=timezone.utc)
    window   = timedelta(days=20)

    all_records: list[dict] = []
    current = start_dt
    while current < end_dt:
        window_end = min(current + window, end_dt)
        try:
            records = hl_post({
                "type": "fundingHistory",
                "coin": coin,
                "startTime": int(current.timestamp() * 1000),
                "endTime":   int(window_end.timestamp() * 1000),
            })
            if isinstance(records, list):
                all_records.extend(records)
        except Exception as e:
            print(f"    funding {current.date()} -> {window_end.date()}: ERROR — {e}")
        current = window_end
        time.sleep(0.15)

    if not all_records:
        return pd.Series(dtype=float)

    df = pd.DataFrame(all_records)
    df["date"] = pd.to_datetime(df["time"].astype(int), unit="ms", utc=True).dt.tz_localize(None).dt.normalize()
    df["fr"] = df["fundingRate"].astype(float)
    daily = df.groupby("date")["fr"].sum()
    weekly = daily.resample("W-FRI").sum()
    return weekly


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # ── Prices ──────────────────────────────────────────────────────────────
    for asset, listing in LISTINGS.items():
        print(f"\n{asset}: HL HIP-3 perp xyz:{asset} from {listing}...")
        df = fetch_weekly_prices(f"xyz:{asset}", listing)
        if df.empty:
            print(f"  WARNING: no candles returned for xyz:{asset}")
            continue
        out_path = OUT_DIR / f"equity_{asset}_hl.csv"
        df.to_csv(out_path, index=False)
        print(f"  Prices saved: {out_path} ({len(df)} weekly bars, {df['date'].min()} -> {df['date'].max()})")

    # ── Funding ─────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("HIP-3 Equity Funding Rates")
    print("=" * 60)
    funding_frames: list[pd.Series] = []
    for asset, listing in LISTINGS.items():
        print(f"\n{asset} (xyz:{asset}): {listing} -> {_last_friday()}")
        weekly = fetch_weekly_funding(f"xyz:{asset}", listing)
        if weekly.empty:
            print(f"  WARNING: no funding data for xyz:{asset}")
            continue
        weekly.name = asset
        funding_frames.append(weekly)
        print(f"  {len(weekly)} weekly rows ({weekly.index[0].date()} -> {weekly.index[-1].date()})")
        print(f"  Non-zero weeks: {(weekly != 0).sum()}/{len(weekly)}")

    if funding_frames:
        funding = pd.concat(funding_frames, axis=1)
        # Drop incomplete trailing Friday
        today = pd.Timestamp(datetime.now(timezone.utc).date())
        funding = funding[funding.index < today]
        funding.index = funding.index.strftime("%Y-%m-%d")
        out_path = OUT_DIR / "equity_funding_hl.csv"
        funding.to_csv(out_path)
        print(f"\nFunding saved: {out_path} ({funding.shape[1]} assets, {funding.shape[0]} weeks)")
    else:
        print("\nNo equity funding data pulled.")


if __name__ == "__main__":
    main()
