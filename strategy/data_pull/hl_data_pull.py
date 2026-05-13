"""
Hyperliquid Main-Dex Historical Data Pull
Fetches: daily close price + weekly summed funding rate for SOL, BNB, HYPE, XMR.
Output:  data/alts/hl_prices.csv         (weekly)
         data/alts/hl_funding_rates.csv  (weekly)
         data/alts/hl_oi_snapshot.csv    (current snapshot only — HL has no historical OI)

Equity perps (COIN/HOOD/CRCL) live on the HIP-3 `xyz` dex and are pulled
separately by `pull_hl_equities.py`.
"""

import requests, sys, time
import pandas as pd
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

def _last_friday() -> str:
    """Most recent complete Friday (no future partial-week buckets)."""
    today = datetime.now(timezone.utc).date()
    fri = today - timedelta(days=(today.weekday() - 4) % 7)
    return fri.strftime("%Y-%m-%d")

HL_URL  = "https://api.hyperliquid.xyz/info"
ASSETS  = ["SOL", "BNB", "HYPE", "XMR"]
START   = "2022-01-01"
END     = _last_friday()
OUT_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "alts"
OUT_DIR.mkdir(parents=True, exist_ok=True)

def hl_post(payload, retries=3):
    for attempt in range(retries):
        try:
            r = requests.post(HL_URL, headers={"Content-Type": "application/json"},
                              json=payload, timeout=20)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            if attempt == retries - 1:
                raise
            print(f"  Retry {attempt+1}: {e}")
            time.sleep(2)

def to_ms(dt_str):
    dt = datetime.strptime(dt_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)

def from_ms(ms):
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")

# ─────────────────────────────────────────────────────────────────────
# 1. Pull daily candles → weekly close price
# ─────────────────────────────────────────────────────────────────────
print("=" * 60)
print("STEP 1 — Pulling daily candles for price data")
print("=" * 60)

price_frames = []

for asset in ASSETS:
    print(f"\n  {asset}: fetching daily candles {START} → {END}...")

    # HL candles: max ~5000 per call, use 1-year windows
    all_candles = []
    current = START
    while current < END:
        next_year = str(int(current[:4]) + 1) + current[4:]
        window_end = min(next_year, END)

        try:
            candles = hl_post({
                "type": "candleSnapshot",
                "req": {
                    "coin": asset,
                    "interval": "1d",
                    "startTime": to_ms(current),
                    "endTime":   to_ms(window_end),
                }
            })
            all_candles.extend(candles)
            print(f"    {current} → {window_end}: {len(candles)} candles")
        except Exception as e:
            print(f"    {current} → {window_end}: ERROR — {e}")

        current = window_end
        time.sleep(0.3)

    if not all_candles:
        print(f"  WARNING: no candles for {asset}")
        continue

    df = pd.DataFrame(all_candles)
    df["date"] = pd.to_datetime(df["t"].astype(int), unit="ms", utc=True).dt.normalize()
    df["close"] = df["c"].astype(float)
    df = df[["date", "close"]].drop_duplicates("date").set_index("date").sort_index()

    # Resample to weekly (Friday close)
    weekly = df["close"].resample("W-FRI").last().dropna()
    weekly.name = asset
    price_frames.append(weekly)
    print(f"  {asset}: {len(df)} daily rows -> {len(weekly)} weekly rows")

prices = pd.concat(price_frames, axis=1)
prices.index = prices.index.strftime("%Y-%m-%d")
prices.to_csv(OUT_DIR / "hl_prices.csv")
print(f"\nSaved: data/alts/hl_prices.csv ({prices.shape})")
print(prices.tail(5).to_string())

# ─────────────────────────────────────────────────────────────────────
# 2. Pull hourly funding rates → weekly average
# ─────────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("STEP 2 — Pulling funding rate history")
print("=" * 60)

funding_frames = []

for asset in ASSETS:
    print(f"\n  {asset}: fetching funding rates {START} → {END}...")

    # Paginate in 20-day windows. HL caps fundingHistory at 500 records per
    # call; hourly funding * 20 days = 480, just under the cap. A larger
    # window silently truncates and the tail of the requested range is lost.
    all_funding = []
    start_dt = datetime.strptime(START, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    end_dt   = datetime.strptime(END,   "%Y-%m-%d").replace(tzinfo=timezone.utc)
    window   = timedelta(days=20)
    current_dt = start_dt

    while current_dt < end_dt:
        window_end_dt = min(current_dt + window, end_dt)
        try:
            records = hl_post({
                "type": "fundingHistory",
                "coin": asset,
                "startTime": int(current_dt.timestamp() * 1000),
                "endTime":   int(window_end_dt.timestamp() * 1000),
            })
            all_funding.extend(records)
            print(f"    {current_dt.strftime('%Y-%m-%d')} → "
                  f"{window_end_dt.strftime('%Y-%m-%d')}: {len(records)} records")
        except Exception as e:
            print(f"    {current_dt.strftime('%Y-%m-%d')}: ERROR — {e}")

        current_dt = window_end_dt
        time.sleep(0.3)

    if not all_funding:
        print(f"  WARNING: no funding data for {asset}")
        continue

    df = pd.DataFrame(all_funding)
    df["date"] = pd.to_datetime(df["time"].astype(int), unit="ms", utc=True).dt.normalize()
    df["funding_rate"] = df["fundingRate"].astype(float)

    # Weekly: sum hourly rates to get weekly total funding cost
    # Also compute weekly average for scoring
    weekly_sum = df.groupby("date")["funding_rate"].sum()  # daily sum (24 hourly)
    weekly_sum = weekly_sum.resample("W-FRI").sum().dropna()  # weekly sum
    weekly_sum.name = asset

    funding_frames.append(weekly_sum)
    print(f"  {asset}: {len(df)} hourly rows -> {len(weekly_sum)} weekly rows")
    print(f"  {asset}: recent weekly funding = {weekly_sum.tail(3).values}")

funding = pd.concat(funding_frames, axis=1)
funding.index = funding.index.strftime("%Y-%m-%d")
funding.to_csv(OUT_DIR / "hl_funding_rates.csv")
print(f"\nSaved: data/alts/hl_funding_rates.csv ({funding.shape})")
print(funding.tail(5).to_string())

# ─────────────────────────────────────────────────────────────────────
# 3. Current OI snapshot (note: HL has no historical OI endpoint)
# ─────────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("STEP 3 — Current OI snapshot")
print("=" * 60)

meta = hl_post({"type": "meta"})
ctx  = hl_post({"type": "metaAndAssetCtxs"})
asset_ctxs = ctx[1]

oi_rows = []
for i, asset_info in enumerate(meta["universe"]):
    if asset_info["name"] in ASSETS:
        c = asset_ctxs[i]
        oi_rows.append({
            "asset": asset_info["name"],
            "open_interest": float(c.get("openInterest", 0)),
            "mark_price":    float(c.get("markPx", 0)),
            "funding_rate":  float(c.get("funding", 0)),
            "as_of": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        })

oi_df = pd.DataFrame(oi_rows)
print(oi_df.to_string(index=False))
oi_df.to_csv(OUT_DIR / "hl_oi_snapshot.csv", index=False)
print(f"\nSaved: data/alts/hl_oi_snapshot.csv")
print("\nNOTE: HL API does not expose historical OI time series.")

print("\n" + "=" * 60)
print("DONE. Files saved to data/alts/")
print("=" * 60)
