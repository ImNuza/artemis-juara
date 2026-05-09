"""
Pull quarterly equity fundamentals from Artemis API for COIN, HOOD, CRCL.
Metrics: TOTAL_REVENUE, TRANSACTION_REVENUE, TRADING_VOLUME, NET_INCOME
"""
import os

import requests
import pandas as pd
from pathlib import Path

API_KEY = os.environ.get("ARTEMIS_API_KEY", "")
BASE_URL = "https://data-svc.artemisxyz.com"
DATA_DIR = Path("data")

EQUITY_IDS = ["coinbase", "robinhood", "circle"]
TICKER_MAP = {"coinbase": "COIN", "robinhood": "HOOD", "circle": "CRCL"}
METRICS = ["TOTAL_REVENUE", "TRANSACTION_REVENUE", "TRADING_VOLUME", "NET_INCOME"]

START = "2022-01-01"
END = "2026-05-06"


def pull_metric(metric, artemis_id):
    url = f"{BASE_URL}/data/{metric}"
    params = {
        "APIKey": API_KEY,
        "artemisIds": artemis_id,
        "startDate": START,
        "endDate": END,
        "granularity": "QUARTER",
    }
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    asset_data = data.get("data", {}).get("artemis_ids", {}).get(artemis_id, {})
    values = asset_data.get(metric, [])
    if isinstance(values, str):
        print(f"  {metric}: {values}")
        return None
    if not values:
        print(f"  {metric}: no data")
        return None
    df = pd.DataFrame(values)
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date")
    df.columns = [f"{TICKER_MAP[artemis_id]}_{metric}"]
    return df


def main():
    DATA_DIR.mkdir(exist_ok=True)

    for metric in METRICS:
        print(f"\nPulling {metric}...")
        pieces = []
        for artemis_id in EQUITY_IDS:
            ticker = TICKER_MAP[artemis_id]
            print(f"  {ticker} ({artemis_id})...")
            df = pull_metric(metric, artemis_id)
            if df is not None:
                pieces.append(df)

        if pieces:
            combined = pd.concat(pieces, axis=1)
            combined = combined.sort_index()
            fname = f"artemis_equity_{metric.lower()}.csv"
            combined.to_csv(DATA_DIR / fname, float_format="%.4f")
            print(f"  Saved {len(combined)} quarters to {fname}")
        else:
            print(f"  No data for {metric}, skipping.")


if __name__ == "__main__":
    main()
