"""Rolling 2-year min-max normalization for each sub-indicator.

The plan specifies a rolling 2-year window to avoid look-ahead bias.
Full-sample normalization would leak future information into past dates.
"""

from __future__ import annotations

import pandas as pd


WINDOW_DAYS = 2 * 365
MIN_PERIODS = 180


def rolling_minmax_normalize(series: pd.Series, invert: bool = False,
                             window: int = WINDOW_DAYS,
                             min_periods: int = MIN_PERIODS) -> pd.Series:
    """Map series to 0-100 using a rolling min-max window.

    100 = at or above the window max (overheated by indicator's reading).
    0 = at or below the window min.

    If invert=True, the mapping is reversed so that low raw values score high.
    Used for the dominance ROC indicator: falling dominance is bullish for alts.
    """
    rolling_min = series.rolling(window, min_periods=min_periods).min()
    rolling_max = series.rolling(window, min_periods=min_periods).max()
    span = (rolling_max - rolling_min).replace(0, pd.NA)
    norm = (series - rolling_min) / span
    norm = norm.clip(0, 1) * 100
    if invert:
        norm = 100 - norm
    return norm


PLAN_INVERSIONS = {  # Option A: per the plan PDF (contrarian / value), ETF dropped
    "mvrv_z": True,
    "puell": True,
    "price_200w_ratio": True,
    "stable_30d": False,
    "dom_proxy_30d_roc": True,
}

TREND_INVERSIONS = {  # Option B: de-invert the cycle indicators (trend / momentum), ETF dropped
    "mvrv_z": False,
    "puell": False,
    "price_200w_ratio": False,
    "stable_30d": False,
    "dom_proxy_30d_roc": True,
}

OPTION_D_INVERSIONS = {  # Option D: trend + Fed balance sheet macro overlay, ETF dropped
    "mvrv_z": False,
    "puell": False,
    "price_200w_ratio": False,
    "stable_30d": False,
    "dom_proxy_30d_roc": True,
    "fed_bs_30d_roc": False,
}


def normalize_all(raw: pd.DataFrame, mode: str = "plan") -> pd.DataFrame:
    """Map all raw indicators to 0-100 using rolling 2-yr min-max.

    mode='plan'  (Option A): plan-PDF spec, contrarian/value
    mode='trend' (Option B): de-inverted valuation, trend/momentum, no macro
    mode='D'     (Option D): Option B + Fed balance sheet macro signal

    Direction conventions (after normalization, 100 = score high):
      etf_7d:           direct     (high inflows = score high in all modes)
      stable_30d:       direct     (rising stables = score high in all modes)
      dom_proxy_30d_roc: inverted  (falling dom = alt rotation = score high)
      fed_bs_30d_roc:   direct     (rising Fed BS = QE = liquidity expansion)
    """
    inv_map = {"plan": PLAN_INVERSIONS, "trend": TREND_INVERSIONS, "D": OPTION_D_INVERSIONS}
    inv = inv_map[mode]
    out = pd.DataFrame(index=raw.index)
    for col, invert in inv.items():
        if col in raw.columns:
            out[col] = rolling_minmax_normalize(raw[col], invert=invert)
    return out
