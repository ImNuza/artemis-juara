"""Load and align all input series for the BTC regime composite."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data" / "btc"
LEGACY_STABLECOIN = BASE_DIR / "archive" / "terminal_csvs" / "Chains - Stablecoin Supply.csv"


def _read_artemis_csv(filename: str, value_col: str) -> pd.Series:
    df = pd.read_csv(DATA_DIR / filename)
    df["date"] = pd.to_datetime(df["date"])
    return df.set_index("date")[value_col].sort_index().rename(value_col)


def load_btc_price() -> pd.Series:
    return _read_artemis_csv("btc_price.csv", "price")


def load_btc_mvrv() -> pd.Series:
    df = pd.read_csv(DATA_DIR / "btc_mvrv.csv")
    df["date"] = pd.to_datetime(df["date"])
    return df.set_index("date")["mvrv_ratio"].sort_index()


def load_btc_fees() -> pd.Series:
    return _read_artemis_csv("btc_fees.csv", "fees")


def load_btc_emissions_native() -> pd.Series:
    return _read_artemis_csv("btc_emissions_native.csv", "gross_emissions_native")


def load_btc_miner_revenue() -> pd.Series:
    """Compute BTC miner revenue (USD) = transaction fees + block emissions in BTC × price."""
    fees = load_btc_fees()
    emissions = load_btc_emissions_native()
    price = load_btc_price()
    df = pd.concat({"fees": fees, "emissions": emissions, "price": price}, axis=1)
    df = df.sort_index()
    revenue = df["fees"].fillna(0) + df["emissions"].fillna(0) * df["price"]
    revenue.name = "miner_revenue_usd"
    return revenue


def load_btc_etf_flows() -> pd.Series:
    return _read_artemis_csv("btc_etf_flows.csv", "etf_flows")


def load_btc_market_cap() -> pd.Series:
    return _read_artemis_csv("btc_market_cap.csv", "mc")


def load_eth_market_cap() -> pd.Series:
    return _read_artemis_csv("eth_market_cap.csv", "mc")


def load_fred_walcl() -> pd.Series:
    """Fed balance sheet (Total Assets, $M, weekly)."""
    df = pd.read_csv(DATA_DIR / "fred_walcl.csv")
    df["date"] = pd.to_datetime(df["date"])
    return df.set_index("date")["walcl"].sort_index()


def load_stablecoin_supply_total() -> pd.Series:
    """Load aggregate stablecoin supply across all tracked chains."""
    df = pd.read_csv(LEGACY_STABLECOIN)
    df.columns = [c.strip().strip('"').replace('﻿', '') for c in df.columns]
    df["DateTime"] = pd.to_datetime(df["DateTime"])
    df = df.set_index("DateTime").sort_index()
    chain_cols = [c for c in df.columns if c != "DateTime"]
    total = df[chain_cols].sum(axis=1, min_count=1)
    total.name = "stablecoin_supply_total"
    total.index.name = "date"
    return total


def load_btc_sopr() -> pd.Series:
    df = pd.read_csv(DATA_DIR / "btc_sopr.csv")
    df["date"] = pd.to_datetime(df["date"])
    return df.set_index("date")["sopr"].sort_index()


def load_btc_funding_binance() -> pd.Series:
    df = pd.read_csv(DATA_DIR / "btc_funding_binance.csv")
    df["date"] = pd.to_datetime(df["date"])
    return df.set_index("date")["funding_rate_avg"].sort_index()


def load_all_inputs() -> pd.DataFrame:
    """Load every series and align onto a common daily index.

    Returns a DataFrame with columns:
      price, mvrv_ratio, miner_revenue, etf_flows, btc_mc, eth_mc, stablecoin_supply
    """
    series = {
        "price": load_btc_price(),
        "mvrv_ratio": load_btc_mvrv(),
        "miner_revenue": load_btc_miner_revenue(),
        "etf_flows": load_btc_etf_flows(),
        "btc_mc": load_btc_market_cap(),
        "eth_mc": load_eth_market_cap(),
        "stablecoin_supply": load_stablecoin_supply_total(),
        "fed_balance_sheet": load_fred_walcl(),
    }
    df = pd.concat(series, axis=1)
    df = df.asfreq("D")
    df = df.ffill()
    return df
