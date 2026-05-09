"""Compute the six raw sub-indicators that feed the BTC composite score.

All raw indicators are returned as pandas Series indexed by daily date.
None of these are normalized yet; normalization happens in normalize.py.

Methodology references in code comments cite the New Idea Change.pdf plan.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def mvrv_zscore(mvrv_ratio: pd.Series, window_days: int = 365 * 4) -> pd.Series:
    """Convert MVRV ratio to a rolling Z-score over a 4-year window.

    The plan specifies "rolling 4-year Z-score window to avoid look-ahead bias".
    """
    mean = mvrv_ratio.rolling(window_days, min_periods=180).mean()
    std = mvrv_ratio.rolling(window_days, min_periods=180).std()
    z = (mvrv_ratio - mean) / std
    z.name = "mvrv_zscore_raw"
    return z


def puell_multiple(miner_revenue: pd.Series) -> pd.Series:
    """Puell Multiple = daily miner revenue / 365d MA of miner revenue.

    Below ~0.5 historically signals cycle bottoms (miners exhausted).
    Above ~4.0 historically signals cycle tops.
    """
    ma_365 = miner_revenue.rolling(365, min_periods=180).mean()
    puell = miner_revenue / ma_365
    puell.name = "puell_multiple_raw"
    return puell


def etf_inflows_7d(etf_flows: pd.Series) -> pd.Series:
    """7-day rolling sum of net ETF flows. Positive = institutional accumulation."""
    s = etf_flows.fillna(0).rolling(7, min_periods=1).sum()
    s.name = "etf_inflows_7d_raw"
    return s


def price_200w_ma_ratio(price: pd.Series) -> pd.Series:
    """Price / 200-week MA. Below 1.0 historically the deep value zone."""
    ma_200w = price.rolling(200 * 7, min_periods=180).mean()
    ratio = price / ma_200w
    ratio.name = "price_200w_ma_ratio_raw"
    return ratio


def stablecoin_supply_delta_30d(supply: pd.Series) -> pd.Series:
    """30-day percent change in total stablecoin supply.

    Rising supply = dry powder accumulating, bullish for crypto deployment.
    """
    delta = supply.pct_change(30)
    delta.name = "stablecoin_delta_30d_raw"
    return delta


def fed_balance_sheet_30d_roc(fed_bs: pd.Series) -> pd.Series:
    """30-day rate of change in Fed total assets.

    Rising Fed balance sheet (QE) = liquidity expansion = bullish for risk assets.
    Falling (QT) = bearish.
    Series is weekly so 30d ROC is essentially 4-week change forward-filled to daily.
    """
    roc = fed_bs.pct_change(30)
    roc.name = "fed_bs_30d_roc_raw"
    return roc


def btc_eth_dominance_proxy_30d_roc(btc_mc: pd.Series, eth_mc: pd.Series) -> pd.Series:
    """30-day rate of change in BTC dominance proxy = BTC_MC / (BTC_MC + ETH_MC).

    True total-market dominance requires aggregating all crypto market caps,
    which needs a paid API. We use BTC vs ETH as a proxy: when BTC dominance
    over the largest alt is rising = risk-off rotation; falling = alt season.

    The plan says "inverted" for this signal: falling dominance scores HIGH
    (bullish for alts). We return the raw 30d ROC; normalization handles the
    inversion in composite.py.
    """
    proxy = btc_mc / (btc_mc + eth_mc)
    roc = proxy.pct_change(30)
    roc.name = "btc_dom_proxy_30d_roc_raw"
    return roc


def compute_all_raw(df: pd.DataFrame) -> pd.DataFrame:
    """Compute all raw sub-indicators on the aligned input DataFrame."""
    out = pd.DataFrame(index=df.index)
    out["mvrv_z"] = mvrv_zscore(df["mvrv_ratio"])
    out["puell"] = puell_multiple(df["miner_revenue"])
    out["price_200w_ratio"] = price_200w_ma_ratio(df["price"])
    out["stable_30d"] = stablecoin_supply_delta_30d(df["stablecoin_supply"])
    out["dom_proxy_30d_roc"] = btc_eth_dominance_proxy_30d_roc(df["btc_mc"], df["eth_mc"])
    if "fed_balance_sheet" in df.columns:
        out["fed_bs_30d_roc"] = fed_balance_sheet_30d_roc(df["fed_balance_sheet"])
    return out
