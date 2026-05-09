"""Threshold sensitivity for the BTC regime gate.

Tests BULL threshold at 50 / 55 / 60 / 65 / 70 (and matching BEAR shifts)
across all three modes (A, B, D). Reports the matrix and saves CSVs.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .backtest import (
    RESULTS_DIR,
    run_buy_hold_btc,
    run_regime_backtest,
)
from .composite import compute_regime_timeline
from .data_loader import load_btc_price


THRESHOLD_SETS = [
    (50, 30),
    (55, 32),
    (60, 35),  # default
    (65, 38),
    (70, 40),
]

MODES = [("plan", "Option A"), ("trend", "Option B"), ("D", "Option D")]


def main():
    price = load_btc_price()
    rows = []

    for mode_key, mode_label in MODES:
        for bull_t, bear_t in THRESHOLD_SETS:
            diag, weekly = compute_regime_timeline(
                mode=mode_key,
                bull_threshold=bull_t,
                bear_threshold=bear_t,
            )
            m = run_regime_backtest(diag, weekly, price,
                                    label=f"{mode_label} BULL>={bull_t}")
            rows.append({
                "mode": mode_label,
                "bull_threshold": bull_t,
                "bear_threshold": bear_t,
                "final_value": round(m["final_value"], 0),
                "ann_return": round(m["ann_return"], 4),
                "sharpe": round(m["sharpe"], 3),
                "max_drawdown": round(m["max_drawdown"], 4),
                "calmar": round(m["calmar"], 3),
            })

    m_btc = run_buy_hold_btc(price)
    rows.append({
        "mode": "BTC B&H",
        "bull_threshold": -1,
        "bear_threshold": -1,
        "final_value": round(m_btc["final_value"], 0),
        "ann_return": round(m_btc["ann_return"], 4),
        "sharpe": round(m_btc["sharpe"], 3),
        "max_drawdown": round(m_btc["max_drawdown"], 4),
        "calmar": round(m_btc["calmar"], 3),
    })

    df = pd.DataFrame(rows)
    df.to_csv(RESULTS_DIR / "threshold_sensitivity.csv", index=False)

    print("=" * 110)
    print("BULL THRESHOLD SENSITIVITY (BTC-only regime backtest, $100K from 2020-01-01)")
    print("=" * 110)
    print(f"{'mode':<12} {'BULL>=':<8} {'BEAR<=':<8} {'final_$':<14} "
          f"{'ann_ret':<10} {'sharpe':<10} {'max_dd':<10} {'calmar':<10}")
    print("-" * 110)
    for r in rows:
        b_t = "" if r['bull_threshold'] == -1 else f"{r['bull_threshold']}"
        be_t = "" if r['bear_threshold'] == -1 else f"{r['bear_threshold']}"
        print(f"{r['mode']:<12} {b_t:<8} {be_t:<8} ${r['final_value']:>11,.0f}  "
              f"{r['ann_return']:>+8.1%}  {r['sharpe']:>+7.2f}   "
              f"{r['max_drawdown']:>+7.1%}   {r['calmar']:>+7.2f}")
    print("=" * 110)
    print(f"\nSaved to {RESULTS_DIR}/threshold_sensitivity.csv")


if __name__ == "__main__":
    main()
