"""Pre-2024 robustness test.

ETF data started Jan 2024. The composite has used etf_7d as a 20% signal
in periods where ETF data didn't exist (NaN-handled by composite_score).
This script verifies the regime classification still works without ETF data
on the 2018-2023 sample by zeroing out the ETF column entirely.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .backtest import (
    RESULTS_DIR,
    run_buy_hold_btc,
    run_regime_backtest,
)
from .composite import (
    OPTION_D_WEIGHTS,
    PLAN_WEIGHTS,
    classify_regime,
    composite_score,
    regime_to_action,
    BULL_THRESHOLD,
    BEAR_THRESHOLD,
)
from .data_loader import load_all_inputs, load_btc_price
from .indicators import compute_all_raw
from .normalize import normalize_all


def compute_regime_no_etf(mode: str = "D") -> tuple[pd.DataFrame, pd.DataFrame]:
    """Same pipeline but drops the ETF column before scoring.
    Re-normalizes weights to compensate for the missing ETF signal."""
    inputs = load_all_inputs()
    raw = compute_all_raw(inputs)
    normalized = normalize_all(raw, mode=mode)

    if "etf_7d" in normalized.columns:
        normalized = normalized.drop(columns=["etf_7d"])

    # Renormalize weights: drop etf_7d, rescale remaining weights to sum to 1
    base_weights = OPTION_D_WEIGHTS if mode == "D" else PLAN_WEIGHTS
    weights = {k: v for k, v in base_weights.items() if k != "etf_7d"}
    total = sum(weights.values())
    weights = {k: v / total for k, v in weights.items()}

    score = composite_score(normalized, weights=weights)
    score_lagged = score.shift(7)
    regime = classify_regime(score_lagged)
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

    weekly_dates = pd.date_range(diag.index.min(), diag.index.max(), freq="W-MON")
    weekly_dates = weekly_dates.intersection(diag.index)
    weekly = diag.loc[weekly_dates, ["btc_score_lagged", "regime", "action"]].copy()
    weekly = weekly.rename(columns={"btc_score_lagged": "btc_score"})
    weekly.index.name = "date"
    weekly = weekly.reset_index()
    return diag, weekly


def main():
    price = load_btc_price()

    diag_full, _ = compute_regime_no_etf(mode="D")  # noqa: just to check it runs
    print("Full pipeline ran without errors. Now backtest...")
    print()

    diag_d_no_etf, weekly_d_no_etf = compute_regime_no_etf(mode="D")
    m_d_no_etf = run_regime_backtest(
        diag_d_no_etf, weekly_d_no_etf, price,
        label="Option D (no ETF signal)"
    )

    diag_b_no_etf, weekly_b_no_etf = compute_regime_no_etf(mode="trend")
    m_b_no_etf = run_regime_backtest(
        diag_b_no_etf, weekly_b_no_etf, price,
        label="Option B (no ETF signal)"
    )

    m_btc = run_buy_hold_btc(price)

    print("=" * 130)
    print("PRE-2024 ROBUSTNESS — strategies built without the ETF Inflows signal")
    print("=" * 130)
    for m in [m_b_no_etf, m_d_no_etf, m_btc]:
        from .backtest import fmt_metrics
        print(fmt_metrics(m))
    print("=" * 130)
    print()

    # Sub-period focus on the pre-2024 window where this matters most
    print("PRE-2024 PERIOD ONLY (2020-01-01 to 2023-12-31):")
    for m in [m_b_no_etf, m_d_no_etf, m_btc]:
        eq = m["equity"].loc["2020-01-01":"2023-12-31"]
        if len(eq) < 5:
            continue
        ret = eq.iloc[-1] / eq.iloc[0] - 1
        rolling_max = eq.cummax()
        dd = ((eq - rolling_max) / rolling_max).min()
        print(f"  {m['label']:<35} period_ret={ret:>+8.1%}  max_dd={dd:>+7.1%}")

    weekly_d_no_etf.to_csv(RESULTS_DIR / "btc_regime_weekly_optionD_no_etf.csv", index=False)
    weekly_b_no_etf.to_csv(RESULTS_DIR / "btc_regime_weekly_optionB_no_etf.csv", index=False)

    print()
    print(f"Saved to {RESULTS_DIR}/")


if __name__ == "__main__":
    main()
