"""Entry point: build the BTC regime timeline, save outputs."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .composite import compute_regime_timeline
from .plots import plot_regime_timeline, plot_subindicator_breakdown


BASE_DIR = Path(__file__).resolve().parents[2]
RESULTS_DIR = BASE_DIR / "results" / "btc_regime"


def run(mode: str = "trend"):
    """Run pipeline. Default mode = 'trend' (Option B), the recommended ship config.
    Override with mode='plan' for Option A or mode='D' for Option D."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    diag, weekly = compute_regime_timeline(mode=mode)

    diag.to_csv(RESULTS_DIR / "btc_composite_daily_full.csv")
    weekly.to_csv(RESULTS_DIR / "btc_regime_weekly.csv", index=False)

    diag_lite_cols = [c for c in diag.columns if c.startswith("norm_")] + [
        "btc_score", "btc_score_lagged", "regime", "action"
    ]
    diag[diag_lite_cols].to_csv(RESULTS_DIR / "btc_composite_daily.csv")

    plot_regime_timeline(diag, weekly, RESULTS_DIR / "regime_timeline.png")
    plot_subindicator_breakdown(diag, RESULTS_DIR / "subindicators_breakdown.png")

    return diag, weekly


if __name__ == "__main__":
    diag, weekly = run()
    print(f"Daily rows: {len(diag)}, weekly rows: {len(weekly)}")
    print(f"Last 10 weekly classifications:")
    print(weekly.tail(10).to_string(index=False))
