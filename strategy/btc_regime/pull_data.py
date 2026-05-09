"""
Pull all data needed for the BTC regime composite score.

Sources:
  Artemis API (data-svc.artemisxyz.com)
    - PRICE: BTC price (used for 200W MA, dominance cross-check)
    - ETF_FLOWS: daily net ETF flows
    - REVENUE: BTC miner revenue (used for Puell Multiple)
    - MC: BTC market cap (used for dominance computation)
  CoinGecko API (free, public)
    - Total crypto market cap (for BTC dominance computation)
  CoinMetrics community data (free, public)
    - Realized cap and MVRV ratio for BTC
  Local existing CSVs
    - archive/coingecko/btc-usd-max.csv (BTC price 200W MA)
    - archive/terminal_csvs/Chains - Stablecoin Supply.csv (stablecoin supply Delta)

Outputs all CSVs to data/btc/.
"""

from __future__ import annotations

import csv
import os
import sys
import time
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Iterable
from urllib.parse import urlencode
from urllib.request import urlopen, Request


BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data" / "btc"
CONFIG_PATH = BASE_DIR / "archive" / "api_exploration" / "config.env"

ARTEMIS_BASE = "https://data-svc.artemisxyz.com"

# Pull a long window so we have warm-up for rolling normalization
START_DATE = "2018-01-01"


def load_api_key() -> str:
    text = CONFIG_PATH.read_text()
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("ARTEMIS_API_KEY"):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise RuntimeError("ARTEMIS_API_KEY not found in config.env")


def load_fred_key() -> str:
    text = CONFIG_PATH.read_text()
    for line in text.splitlines():
        line = line.strip()
        # accept FRED_API_KEY or the typo FREAD_API_KEY
        if line.startswith("FRED_API_KEY") or line.startswith("FREAD_API_KEY"):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise RuntimeError("FRED_API_KEY not found in config.env")


def http_get_json(url: str, retries: int = 3, timeout: int = 60) -> dict:
    last_err = None
    for attempt in range(retries):
        try:
            req = Request(url, headers={
                "Accept": "application/json",
                "User-Agent": "Mozilla/5.0 (compatible; ArtemisRegimeBot/1.0)",
            })
            with urlopen(req, timeout=timeout) as resp:
                import json as _json
                return _json.loads(resp.read().decode("utf-8"))
        except Exception as err:
            last_err = err
            time.sleep(2 ** attempt)
    raise RuntimeError(f"GET failed after {retries} retries: {url} -> {last_err}")


def fetch_artemis_metric(api_key: str, asset_id: str, metric: str,
                         start: str, end: str) -> list[tuple[str, float]]:
    qs = urlencode({
        "APIKey": api_key,
        "artemisIds": asset_id,
        "startDate": start,
        "endDate": end,
    })
    url = f"{ARTEMIS_BASE}/data/{metric}?{qs}"
    payload = http_get_json(url)
    series = payload.get("data", {}).get("artemis_ids", {}).get(asset_id, {}).get(metric, [])
    rows = []
    for entry in series:
        d = entry.get("date")
        v = entry.get("val")
        if d is None or v is None:
            continue
        rows.append((str(d)[:10], float(v)))
    rows.sort(key=lambda r: r[0])
    return rows


def write_csv(path: Path, header: tuple[str, ...], rows: Iterable[tuple]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        for row in rows:
            w.writerow(row)
            n += 1
    return n


def pull_artemis_btc(api_key: str, end_date: str) -> dict[str, int]:
    metrics = {
        "PRICE": "btc_price.csv",
        "ETF_FLOWS": "btc_etf_flows.csv",
        "CUMULATIVE_ETF_FLOW": "btc_etf_cumulative.csv",
        "FEES": "btc_fees.csv",
        "GROSS_EMISSIONS_NATIVE": "btc_emissions_native.csv",
        "MC": "btc_market_cap.csv",
        "CIRCULATING_SUPPLY_NATIVE": "btc_supply.csv",
    }
    results = {}
    for metric, filename in metrics.items():
        try:
            rows = fetch_artemis_metric(api_key, "bitcoin", metric, START_DATE, end_date)
            n = write_csv(DATA_DIR / filename, ("date", metric.lower()), rows)
            results[metric] = n
        except Exception as err:
            results[metric] = f"ERROR: {err}"
    return results


def pull_artemis_eth_mc(api_key: str, end_date: str) -> int:
    """Pull ETH market cap (used to compute BTC vs ETH ratio as a dominance proxy)."""
    rows = fetch_artemis_metric(api_key, "ethereum", "MC", START_DATE, end_date)
    return write_csv(DATA_DIR / "eth_market_cap.csv", ("date", "mc"), rows)


def fetch_coingecko_btc_dominance(end_date: str) -> list[tuple[str, float]]:
    """Pull total crypto market cap and BTC market cap, compute dominance daily."""
    url = "https://api.coingecko.com/api/v3/global"
    payload = http_get_json(url)
    current_btc_dom = payload.get("data", {}).get("market_cap_percentage", {}).get("btc")
    rows = []
    if current_btc_dom is not None:
        rows.append((end_date, float(current_btc_dom)))
    return rows


def fetch_coingecko_btc_dominance_history(end_date: str) -> list[tuple[str, float]]:
    """Pull historical BTC dominance via CoinGecko coins/bitcoin endpoint with market cap.
    We compute dominance from BTC market cap / total crypto market cap.
    """
    end_ts = int(datetime.strptime(end_date, "%Y-%m-%d").timestamp())
    start_ts = int(datetime.strptime(START_DATE, "%Y-%m-%d").timestamp())
    url = (
        "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart/range"
        f"?vs_currency=usd&from={start_ts}&to={end_ts}"
    )
    payload = http_get_json(url)
    btc_mcaps = payload.get("market_caps", [])
    rows = []
    for ts_ms, mcap in btc_mcaps:
        d = datetime.utcfromtimestamp(ts_ms / 1000).date().isoformat()
        rows.append((d, float(mcap)))
    return rows


def fetch_fred_series(api_key: str, series_id: str, end_date: str) -> list[tuple[str, float]]:
    """Pull a FRED time series by series_id. Returns daily-aligned (date, value) pairs.
    The FRED API returns observations in series-native frequency. Caller forward-fills."""
    qs = urlencode({
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
        "observation_start": START_DATE,
        "observation_end": end_date,
    })
    url = f"https://api.stlouisfed.org/fred/series/observations?{qs}"
    payload = http_get_json(url)
    rows = []
    for obs in payload.get("observations", []):
        d = obs.get("date")
        v = obs.get("value")
        if d is None or v in (None, ".", ""):
            continue
        try:
            rows.append((d, float(v)))
        except ValueError:
            continue
    rows.sort(key=lambda r: r[0])
    return rows


def fetch_coinmetrics_mvrv(end_date: str) -> list[tuple[str, float]]:
    """CoinMetrics community data has MVRV-like indicators. Use CapMVRVCur if available.
    Free download: https://community-api.coinmetrics.io/v4/timeseries/asset-metrics
    """
    url = (
        "https://community-api.coinmetrics.io/v4/timeseries/asset-metrics"
        f"?assets=btc&metrics=CapMVRVCur&start_time={START_DATE}&end_time={end_date}"
        "&frequency=1d&page_size=10000&pretty=false"
    )
    rows = []
    next_url = url
    while next_url:
        payload = http_get_json(next_url)
        for entry in payload.get("data", []):
            d = entry.get("time", "")[:10]
            v = entry.get("CapMVRVCur")
            if d and v is not None:
                rows.append((d, float(v)))
        next_url = payload.get("next_page_url")
    return rows


def main():
    api_key = load_api_key()
    end_date = date.today().isoformat()
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Data dir: {DATA_DIR}")
    print(f"Window: {START_DATE} to {end_date}")
    print()

    print("[1/3] Pulling Artemis BTC metrics...")
    artemis_results = pull_artemis_btc(api_key, end_date)
    for metric, result in artemis_results.items():
        print(f"  {metric}: {result} rows" if isinstance(result, int) else f"  {metric}: {result}")
    print()

    print("[2/3] Pulling CoinGecko BTC market cap (for dominance)...")
    try:
        rows = fetch_coingecko_btc_dominance_history(end_date)
        n = write_csv(DATA_DIR / "btc_mcap_coingecko.csv", ("date", "btc_market_cap_usd"), rows)
        print(f"  btc_mcap_coingecko: {n} rows")
    except Exception as err:
        print(f"  btc_mcap_coingecko: ERROR {err}")
    print()

    print("[3/4] Pulling CoinMetrics MVRV...")
    try:
        rows = fetch_coinmetrics_mvrv(end_date)
        n = write_csv(DATA_DIR / "btc_mvrv.csv", ("date", "mvrv_ratio"), rows)
        print(f"  btc_mvrv: {n} rows")
    except Exception as err:
        print(f"  btc_mvrv: ERROR {err}")
    print()

    print("[4/4] Pulling FRED macro series...")
    try:
        fred_key = load_fred_key()
        for series_id, filename, label in [
            ("WALCL", "fred_walcl.csv", "Fed balance sheet (weekly)"),
            ("M2SL", "fred_m2sl.csv", "M2 money supply (monthly)"),
            ("WTREGEN", "fred_wtregen.csv", "Treasury General Account (weekly)"),
        ]:
            try:
                rows = fetch_fred_series(fred_key, series_id, end_date)
                n = write_csv(DATA_DIR / filename, ("date", series_id.lower()), rows)
                print(f"  {series_id}: {n} rows ({label})")
            except Exception as err:
                print(f"  {series_id}: ERROR {err}")
    except Exception as err:
        print(f"  FRED skipped: {err}")
    print()

    print("Done.")


if __name__ == "__main__":
    main()
