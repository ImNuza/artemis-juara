"""
Bybit Funding Rate Backfill — SOL / BNB / XMR.

Hyperliquid funding history starts late for some assets in our universe,
leaving the funding factor scoring those assets neutral-50 (no signal)
for years of the backtest. This script pulls Bybit linear-perp funding
back to 2022 and splices it with HL funding at each asset's HL-listing
date, mirroring the price-data hierarchy in CLAUDE.md decision #7.

HL is venue-correct (we trade there). Bybit is the closest cross-venue
proxy for what HL funding would have looked like pre-listing.

Outputs
  data/alts/hl_only_funding_rates.csv  — backup of HL-only series (one-time)
  data/alts/bybit_funding_rates.csv    — raw Bybit weekly (audit trail)
  data/alts/hl_funding_rates.csv       — OVERWRITTEN with spliced series
                                         (downstream code unchanged)
"""

import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pandas as pd
import requests

sys.stdout.reconfigure(encoding="utf-8")

BYBIT_URL = "https://api.bybit.com/v5/market/funding/history"
ASSETS    = ["SOL", "BNB", "XMR"]
SYMBOL    = {"SOL": "SOLUSDT", "BNB": "BNBUSDT", "XMR": "XMRUSDT"}
START     = "2022-01-01"

def _last_friday() -> str:
    """Most recent complete Friday (no future partial-week buckets)."""
    today = datetime.now(timezone.utc).date()
    fri = today - timedelta(days=(today.weekday() - 4) % 7)
    return fri.strftime("%Y-%m-%d")

END       = _last_friday()

DATA_DIR       = Path(__file__).resolve().parent.parent.parent / "data" / "alts"
HL_PATH        = DATA_DIR / "hl_funding_rates.csv"
HL_BACKUP_PATH = DATA_DIR / "hl_only_funding_rates.csv"
BYBIT_PATH     = DATA_DIR / "bybit_funding_rates.csv"


def to_ms(dt_str: str) -> int:
    dt = datetime.strptime(dt_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def fetch_bybit_funding(symbol: str, start_ms: int, end_ms: int) -> list[dict]:
    """Page backwards through Bybit funding history (200 records per call, newest first)."""
    out: list[dict] = []
    cursor_end = end_ms
    while True:
        try:
            r = requests.get(
                BYBIT_URL,
                params={
                    "category": "linear",
                    "symbol": symbol,
                    "startTime": start_ms,
                    "endTime": cursor_end,
                    "limit": 200,
                },
                timeout=15,
            )
            r.raise_for_status()
            records = r.json().get("result", {}).get("list", [])
        except Exception as e:
            print(f"    ERROR: {e}")
            break
        if not records:
            break
        out.extend(records)
        oldest_ts = int(records[-1]["fundingRateTimestamp"])
        if oldest_ts <= start_ms or len(records) < 200:
            break
        cursor_end = oldest_ts - 1
        time.sleep(0.15)
    return out


def first_nonzero_date(s: pd.Series) -> pd.Timestamp | None:
    """First date where the asset has REAL HL funding (non-NaN AND non-zero).
    NaN must be filtered explicitly — `s != 0.0` evaluates NaN→NaN→falsy in
    pandas mask filtering for some operations but slips through here, so we
    `.dropna()` first."""
    valid = s.dropna()
    valid = valid[valid != 0.0]
    return valid.index[0] if len(valid) else None


def main() -> None:
    print("=" * 60)
    print("Bybit Funding Backfill — SOL / BNB / XMR")
    print("=" * 60)

    hl = pd.read_csv(HL_PATH, parse_dates=["date"], index_col="date").sort_index()
    if hl.index.tz is not None:
        hl.index = hl.index.tz_localize(None)

    # One-time HL-only backup so the original is preserved for audit.
    if not HL_BACKUP_PATH.exists():
        hl.to_csv(HL_BACKUP_PATH)
        print(f"Saved HL-only backup: {HL_BACKUP_PATH.name}")
    else:
        print(f"HL-only backup already present: {HL_BACKUP_PATH.name}")

    # Detect each asset's HL listing date (first non-zero funding row).
    cutoffs: dict[str, pd.Timestamp | None] = {}
    print("\nHL listing cutoffs (first non-zero funding):")
    for asset in ASSETS:
        cutoffs[asset] = first_nonzero_date(hl[asset]) if asset in hl.columns else None
        print(f"  {asset}: {cutoffs[asset].date() if cutoffs[asset] is not None else 'NEVER'}")

    # ── Pull Bybit funding ──────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("Pulling Bybit funding (linear USDT perps)")
    print("=" * 60)

    bybit_frames: list[pd.Series] = []
    for asset in ASSETS:
        sym = SYMBOL[asset]
        print(f"\n  {asset} ({sym}): {START} → {END}")
        records = fetch_bybit_funding(sym, to_ms(START), to_ms(END))
        if not records:
            print("    no records")
            continue
        df = pd.DataFrame(records)
        df["date"] = (
            pd.to_datetime(df["fundingRateTimestamp"].astype(int), unit="ms", utc=True)
            .dt.tz_convert(None)
            .dt.normalize()
        )
        df["funding_rate"] = df["fundingRate"].astype(float)
        daily = df.groupby("date")["funding_rate"].sum()
        weekly = daily.resample("W-FRI").sum()
        weekly.name = asset
        bybit_frames.append(weekly)
        print(
            f"    {len(df)} 8h records → {len(weekly)} weekly rows "
            f"({weekly.index[0].date()} → {weekly.index[-1].date()})"
        )

    if not bybit_frames:
        print("\nNo Bybit data pulled. Aborting.")
        return

    bybit = pd.concat(bybit_frames, axis=1)

    # Drop incomplete trailing Friday (today is mid-week → that Friday's sum is partial).
    today = pd.Timestamp(datetime.now(timezone.utc).date())
    bybit = bybit[bybit.index < today]

    bybit_out = bybit.copy()
    bybit_out.index = bybit_out.index.strftime("%Y-%m-%d")
    bybit_out.to_csv(BYBIT_PATH)
    print(f"\nSaved Bybit raw weekly: {BYBIT_PATH.name}")

    # ── Splice ───────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("Splicing: Bybit pre-cutoff, HL from cutoff onwards")
    print("=" * 60)

    union_idx = hl.index.union(bybit.index).sort_values()
    spliced = pd.DataFrame(index=union_idx)

    for asset in hl.columns:
        hl_col = hl[asset].reindex(union_idx)
        if asset in ASSETS and asset in bybit.columns:
            by_col = bybit[asset].reindex(union_idx)
            cutoff = cutoffs[asset]
            if cutoff is None:
                spliced[asset] = by_col
                kept_by = by_col.notna().sum()
                print(f"  {asset}: no HL data — Bybit only ({kept_by} weeks)")
            else:
                spliced[asset] = by_col.where(union_idx < cutoff, hl_col)
                n_by = ((union_idx < cutoff) & by_col.notna()).sum()
                n_hl = ((union_idx >= cutoff) & hl_col.notna()).sum()
                print(f"  {asset}: Bybit {n_by} weeks before {cutoff.date()}, HL {n_hl} weeks after")
        else:
            spliced[asset] = hl_col
            print(f"  {asset}: no Bybit backfill — HL only")

    spliced = spliced.fillna(0.0)
    spliced.index = spliced.index.strftime("%Y-%m-%d")
    spliced.to_csv(HL_PATH)
    print(f"\nSaved spliced funding: {HL_PATH.name}  shape={spliced.shape}")
    print("\nHead (3) and tail (3) of spliced series:")
    print(spliced.head(3).to_string())
    print("...")
    print(spliced.tail(3).to_string())


if __name__ == "__main__":
    main()
