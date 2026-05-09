"""Compute the BTC composite valuation score and regime classification.

Output schema for the weekly regime CSV (the contract that Layer 2 reads):
  date,btc_score,regime,action
  YYYY-MM-DD,float,{BULL|BEAR|NEUTRAL},{DEPLOY_ALTS|EXIT|HOLD}

T-1 lag is applied: the score generated for week T uses signals available at
the close of week T-1. This is the "single biggest protection against
look-ahead bias" called out in the plan PDF.
"""

from __future__ import annotations

import pandas as pd

from .data_loader import load_all_inputs
from .indicators import compute_all_raw
from .normalize import normalize_all


PLAN_WEIGHTS = {  # Used by Options A and B (5 signals, sum to 1.0, ETF dropped May 5)
    "mvrv_z": 0.30,
    "puell": 0.25,
    "price_200w_ratio": 0.20,
    "stable_30d": 0.15,
    "dom_proxy_30d_roc": 0.10,
}

OPTION_D_WEIGHTS = {  # 6 signals: valuation + Fed macro, ETF dropped May 5
    "mvrv_z": 0.25,
    "puell": 0.20,
    "price_200w_ratio": 0.10,
    "stable_30d": 0.15,
    "dom_proxy_30d_roc": 0.10,
    "fed_bs_30d_roc": 0.20,
}

WEIGHTS_BY_MODE = {
    "plan": PLAN_WEIGHTS,
    "trend": PLAN_WEIGHTS,
    "D": OPTION_D_WEIGHTS,
}

BULL_THRESHOLD = 60
BEAR_THRESHOLD = 35


def composite_score(normalized: pd.DataFrame, weights: dict[str, float] = None) -> pd.Series:
    weights = weights or PLAN_WEIGHTS
    weighted_sum = pd.Series(0.0, index=normalized.index)
    weight_total = pd.Series(0.0, index=normalized.index)
    for col, w in weights.items():
        if col not in normalized.columns:
            continue
        s = normalized[col]
        contrib = s.fillna(0) * w
        weight_total = weight_total + s.notna().astype(float) * w
        weighted_sum = weighted_sum + contrib
    score = weighted_sum / weight_total.replace(0, pd.NA)
    return score


def classify_regime(score: pd.Series, bull: float = BULL_THRESHOLD,
                    bear: float = BEAR_THRESHOLD) -> pd.Series:
    def _label(v):
        if pd.isna(v):
            return "NA"
        if v >= bull:
            return "BULL"
        if v <= bear:
            return "BEAR"
        return "NEUTRAL"

    return score.apply(_label)


def regime_to_action(regime: str) -> str:
    return {
        "BULL": "DEPLOY_ALTS",
        "BEAR": "EXIT",
        "NEUTRAL": "HOLD",
    }.get(regime, "NA")


def compute_regime_timeline(weekday: str = "MON",
                            apply_t_minus_1_lag: bool = True,
                            mode: str = "plan",
                            bull_threshold: float = BULL_THRESHOLD,
                            bear_threshold: float = BEAR_THRESHOLD,
                            ) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Run the full pipeline. Returns (daily_diagnostic_df, weekly_regime_df).

    mode: 'plan' for Option A (contrarian/value), 'trend' for Option B (trend/momentum).

    daily_diagnostic_df: every column for inspection
      [raw_..., norm_..., btc_score, regime, action]

    weekly_regime_df: the contract for Layer 2
      [date, btc_score, regime, action]
    """
    inputs = load_all_inputs()
    raw = compute_all_raw(inputs)
    normalized = normalize_all(raw, mode=mode)

    weights = WEIGHTS_BY_MODE.get(mode, PLAN_WEIGHTS)
    score = composite_score(normalized, weights=weights)

    if apply_t_minus_1_lag:
        score_lagged = score.shift(7)
    else:
        score_lagged = score

    regime = classify_regime(score_lagged, bull=bull_threshold, bear=bear_threshold)
    action = regime.apply(regime_to_action)

    diag = pd.concat([
        inputs.add_prefix("input_"),
        raw.add_prefix("raw_"),
        normalized.add_prefix("norm_"),
        score.rename("btc_score"),
        score_lagged.rename("btc_score_lagged"),
        regime.rename("regime"),
        action.rename("action"),
    ], axis=1)

    weekly_dates = pd.date_range(diag.index.min(), diag.index.max(), freq=f"W-{weekday}")
    weekly_dates = weekly_dates.intersection(diag.index)
    weekly = diag.loc[weekly_dates, ["btc_score_lagged", "regime", "action"]].copy()
    weekly = weekly.rename(columns={"btc_score_lagged": "btc_score"})
    weekly.index.name = "date"
    weekly = weekly.reset_index()

    return diag, weekly
