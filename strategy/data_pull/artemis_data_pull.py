"""
Pull on-chain metrics from Artemis API for alt factor engine.

Endpoint: https://data-svc.artemisxyz.com/data/{METRIC}
Params:   APIKey, artemisIds, startDate, endDate
Response: {"data": {"artemis_ids": {asset: {METRIC: [{date, val}, ...]}}}}

Metrics pulled:
  FEES  -- daily protocol fees (USD). Available: solana, bnb (2022+), hyperliquid (Dec 2024+)
  DAU   -- daily active users.      Available: solana, bnb (2022+), hyperliquid (Dec 2024+)
  XMR / equities: FEES and DAU not available

Asset ID notes:
  BNB = "bnb" (NOT "binancecoin" -- wrong ID for on-chain metrics)

Outputs (weekly, Friday-aligned):
  data/artemis_fees_weekly.csv  -- SOL, BNB, HYPE (weekly summed fees USD)
  data/artemis_dau_weekly.csv   -- SOL, BNB, HYPE (weekly mean DAU)
"""

import json
import os
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd

API_KEY = os.environ.get("ARTEMIS_API_KEY", "")
BASE_URL = "https://data-svc.artemisxyz.com"
DATA_DIR = Path("data")
START = "2022-01-01"
END   = "2026-01-31"

ASSETS = {
    "solana":      "SOL",
    "hyperliquid": "HYPE",
}

ASSET_START = {
    "solana":      "2022-01-01",
    "hyperliquid": "2024-12-01",
}


def fetch(asset_id: str, metric: str, start: str, end: str, retries: int = 3) -> list[dict]:
    qs = urlencode({
        "APIKey":     API_KEY,
        "artemisIds": asset_id,
        "startDate":  start,
        "endDate":    end,
    })
    url = f"{BASE_URL}/data/{metric}?{qs}"
    for attempt in range(retries):
        try:
            req = Request(url, headers={"Accept": "application/json",
                                        "User-Agent": "ArtemisCompBot/1.0"})
            with urlopen(req, timeout=60) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            series = (payload
                      .get("data", {})
                      .get("artemis_ids", {})
                      .get(asset_id, {})
                      .get(metric, []))
            if isinstance(series, str):
                print(f"  [{asset_id}] {metric}: {series}")
                return []
            rows = [(r["date"][:10], r["val"])
                    for r in series if r.get("val") is not None]
            return rows
        except Exception as e:
            if attempt == retries - 1:
                print(f"  [{asset_id}] {metric}: FAILED after {retries} tries -- {e}")
                return []
            time.sleep(2 ** attempt)
    return []


def to_weekly(rows: list[tuple], agg: str) -> pd.Series:
    if not rows:
        return pd.Series(dtype=float)
    df = pd.DataFrame(rows, columns=["date", "val"])
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()
    s = df["val"]
    if agg == "sum":
        return s.resample("W-FRI").sum()
    return s.resample("W-FRI").mean()


def pull_metric(metric: str, agg: str, out_filename: str) -> None:
    print(f"\n{'='*55}")
    print(f"Pulling {metric} (weekly {agg})")
    print(f"{'='*55}")

    frames = {}
    for artemis_id, ticker in ASSETS.items():
        asset_start = ASSET_START[artemis_id]
        print(f"  {ticker} ({artemis_id}): {asset_start} to {END} ...")
        rows = fetch(artemis_id, metric, asset_start, END)
        if rows:
            weekly = to_weekly(rows, agg)
            frames[ticker] = weekly
            print(f"    {len(rows)} daily rows -> {len(weekly)} weekly rows")
            print(f"    first: {weekly.index[0].date()}  last: {weekly.index[-1].date()}")
        else:
            print(f"    no data")

    if not frames:
        print(f"  No data for any asset. Skipping {out_filename}.")
        return

    out = pd.concat(frames, axis=1)
    out.index = out.index.strftime("%Y-%m-%d")
    out.index.name = "date"
    out_path = DATA_DIR / out_filename
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(out_path)
    print(f"\nSaved: {out_path}  shape={out.shape}")
    print(out.tail(5).to_string())


def main():
    DATA_DIR.mkdir(exist_ok=True)
    pull_metric("FEES", "sum",  "artemis_fees_weekly.csv")
    pull_metric("DAU",  "mean", "artemis_dau_weekly.csv")
    print("\nDone. On-chain data for SOL and HYPE saved to data/.")
    print("XMR / equities: FEES and DAU not available in Artemis.")
    print("BNB: intentionally excluded.")


if __name__ == "__main__":
    main()
