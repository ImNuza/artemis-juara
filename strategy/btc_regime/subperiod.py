"""Sub-period breakdown of the regime backtest.

Splits 2020-now into discrete macro windows and reports each strategy's
performance separately. This is what judges call "regime stability check":
a strategy that wins overall but loses badly in one regime is not robust.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .backtest import (
    RESULTS_DIR,
    START_CAPITAL,
    run_buy_hold_btc,
    run_regime_backtest,
)
from .composite import compute_regime_timeline
from .data_loader import load_btc_price


SUB_PERIODS = [
    ("2020 COVID + recovery", "2020-01-01", "2020-12-31"),
    ("2021 bull cycle peak", "2021-01-01", "2021-12-31"),
    ("2022 bear (Luna/FTX)", "2022-01-01", "2022-12-31"),
    ("2023 recovery", "2023-01-01", "2023-12-31"),
    ("2024 ETF + halving rally", "2024-01-01", "2024-12-31"),
    ("2025 Trump rally peak", "2025-01-01", "2025-12-31"),
    ("2026 YTD drawdown", "2026-01-01", "2026-12-31"),
]


def slice_metrics(holdings_idx_value: pd.Series, label: str,
                   period_label: str, start: str, end: str) -> dict:
    eq = holdings_idx_value.loc[start:end].dropna()
    if len(eq) < 5:
        return {"label": label, "period": period_label, "n_days": 0,
                "ret": float("nan"), "sharpe": float("nan"),
                "max_dd": float("nan"), "start_val": np.nan, "end_val": np.nan}
    rets = eq.pct_change().dropna()
    period_ret = eq.iloc[-1] / eq.iloc[0] - 1
    ann_ret = (1 + period_ret) ** (365.25 / max(len(eq), 1)) - 1
    ann_vol = rets.std() * np.sqrt(365)
    sharpe = ann_ret / ann_vol if ann_vol > 0 else 0
    rolling_max = eq.cummax()
    dd = (eq - rolling_max) / rolling_max
    max_dd = dd.min()
    return {
        "label": label,
        "period": period_label,
        "n_days": len(eq),
        "ret": period_ret,
        "ann_ret": ann_ret,
        "sharpe": sharpe,
        "max_dd": max_dd,
        "start_val": eq.iloc[0],
        "end_val": eq.iloc[-1],
    }


def main():
    price = load_btc_price()
    diag_a, weekly_a = compute_regime_timeline(mode="plan")
    diag_b, weekly_b = compute_regime_timeline(mode="trend")
    diag_d, weekly_d = compute_regime_timeline(mode="D")

    m_a = run_regime_backtest(diag_a, weekly_a, price, label="Option A")
    m_b = run_regime_backtest(diag_b, weekly_b, price, label="Option B")
    m_d = run_regime_backtest(diag_d, weekly_d, price, label="Option D")
    m_h = run_buy_hold_btc(price, label="BTC B&H")

    rows = []
    for m in [m_a, m_b, m_d, m_h]:
        for period, start, end in SUB_PERIODS:
            r = slice_metrics(m["equity"], m["label"], period, start, end)
            rows.append(r)

    df = pd.DataFrame(rows)
    pivot_ret = df.pivot_table(index="period", columns="label", values="ret", sort=False)
    pivot_sharpe = df.pivot_table(index="period", columns="label", values="sharpe", sort=False)
    pivot_dd = df.pivot_table(index="period", columns="label", values="max_dd", sort=False)

    pivot_ret = pivot_ret[["Option A", "Option B", "Option D", "BTC B&H"]]
    pivot_sharpe = pivot_sharpe[["Option A", "Option B", "Option D", "BTC B&H"]]
    pivot_dd = pivot_dd[["Option A", "Option B", "Option D", "BTC B&H"]]

    print("=" * 90)
    print("PERIOD RETURN")
    print("=" * 90)
    print(pivot_ret.to_string(float_format=lambda x: f"{x:>+8.1%}" if pd.notna(x) else "  NA   "))
    print()
    print("=" * 90)
    print("PERIOD SHARPE")
    print("=" * 90)
    print(pivot_sharpe.to_string(float_format=lambda x: f"{x:>+6.2f}" if pd.notna(x) else "  NA  "))
    print()
    print("=" * 90)
    print("PERIOD MAX DRAWDOWN")
    print("=" * 90)
    print(pivot_dd.to_string(float_format=lambda x: f"{x:>+7.1%}" if pd.notna(x) else "  NA   "))

    df.to_csv(RESULTS_DIR / "subperiod_breakdown.csv", index=False)
    pivot_ret.to_csv(RESULTS_DIR / "subperiod_returns.csv")
    pivot_sharpe.to_csv(RESULTS_DIR / "subperiod_sharpe.csv")
    pivot_dd.to_csv(RESULTS_DIR / "subperiod_drawdown.csv")
    print()
    print(f"Saved to {RESULTS_DIR}/")


if __name__ == "__main__":
    main()
