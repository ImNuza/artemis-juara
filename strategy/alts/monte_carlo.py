"""
Monte Carlo Robustness Analysis - Regime-Gated Alt Factor Strategy
Artemis Quant Competition Track #1

Randomizes rebalance day, bull threshold, and asset dropout for each of N runs
to test strategy robustness.
"""

import pandas as pd
import numpy as np
import random
import matplotlib.pyplot as plt
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
import backtest as bt

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
RESULTS_DIR = ROOT_DIR / "results" / "integrated"

random.seed(42)
np.random.seed(42)

N_RUNS = 250
REGIME_CSV = bt.DATA_DIR / "btc_regime_weekly_optionB.csv"
DAY_OFFSETS = {"Mon": -4, "Tue": -3, "Wed": -2, "Thu": -1}
REBALANCE_DAYS = list(DAY_OFFSETS.keys())
investable_assets = [a for a in bt.ALT_ASSETS if a not in bt.SHADOW_ASSETS]

WEEKS_PER_YEAR = 52.0

OUTPUT_DIR = ROOT_DIR / "results" / "integrated"

# ── Metrics Helper ─────────────────────────────────────────────────────────────


def compute_numeric_metrics(equity_curve: pd.Series) -> dict:
    """Compute raw numeric performance metrics from an equity curve.

    Returns dict with float keys: sharpe, max_dd, ann_return, final_equity.
    Returns all zeros if fewer than 2 weekly return observations.
    """
    weekly_returns = equity_curve.pct_change().dropna()
    if len(weekly_returns) < 2:
        return {"sharpe": 0.0, "max_dd": 0.0, "ann_return": 0.0, "final_equity": 0.0}

    initial = equity_curve.iloc[0]
    final = equity_curve.iloc[-1]
    n_weeks = len(weekly_returns)

    ann_return = (final / initial) ** (WEEKS_PER_YEAR / n_weeks) - 1 if initial > 0 else 0.0
    ann_vol = weekly_returns.std() * np.sqrt(WEEKS_PER_YEAR)
    sharpe = ann_return / ann_vol if ann_vol > 0 else 0.0

    peak = equity_curve.expanding().max()
    drawdown = (equity_curve - peak) / peak
    max_dd = drawdown.min()

    return {
        "sharpe": float(sharpe),
        "max_dd": float(max_dd),
        "ann_return": float(ann_return),
        "final_equity": float(equity_curve.iloc[-1]),
    }


# ── Main ───────────────────────────────────────────────────────────────────────


def main():
    print("=" * 60)
    print("Monte Carlo Robustness Analysis")
    print("=" * 60)

    # 3. Pre-load data once
    print("\nLoading data...")
    base_prices = bt.load_prices(bt.PRICES_PATH)
    base_funding = bt.load_funding(bt.FUNDING_PATH)
    fees = bt.load_artemis_weekly(bt.FEES_PATH)
    dau = bt.load_artemis_weekly(bt.DAU_PATH)
    btc_price = bt.load_btc_price()
    base_regime = bt.load_ImNuza_regime(REGIME_CSV, btc_price)
    base_equity_rev = bt.load_equity_quarterly(bt.EQUITY_REVENUE_PATH, base_prices.index)

    print(f"  Price weeks: {len(base_prices)}")
    print(f"  Investable assets ({len(investable_assets)}): {investable_assets}")
    print(f"  Regime weeks: {len(base_regime)}")
    print(f"  Running {N_RUNS} iterations...\n")

    # 5. Main loop
    results = []

    for run_id in range(1, N_RUNS + 1):
        rebalance_day = "Unknown"
        bull_threshold = bt.BULL_THRESHOLD
        dropped_label = ""
        original_bull = bt.BULL_THRESHOLD

        try:
            # a. Randomize parameters
            rebalance_day = random.choice(REBALANCE_DAYS)
            offset = DAY_OFFSETS[rebalance_day]
            bull_threshold = bt.BULL_THRESHOLD + random.randint(-3, 3)
            n_drop = random.randint(1, 2)
            dropped = random.sample(investable_assets, n_drop)
            dropped_label = ", ".join(dropped)

            # b. Shift all DataFrames by offset days
            prices = base_prices.copy()
            prices.index = prices.index + pd.Timedelta(days=offset)

            funding = base_funding.copy()
            funding.index = funding.index + pd.Timedelta(days=offset)

            regime = base_regime.copy()
            regime.index = regime.index + pd.Timedelta(days=offset)

            fees_run = fees.copy()
            if not fees_run.empty:
                fees_run.index = fees_run.index + pd.Timedelta(days=offset)

            dau_run = dau.copy()
            if not dau_run.empty:
                dau_run.index = dau_run.index + pd.Timedelta(days=offset)

            equity_rev = base_equity_rev.copy()
            if not equity_rev.empty:
                equity_rev.index = equity_rev.index + pd.Timedelta(days=offset)

            # c. Drop selected assets from prices and funding
            prices = prices.drop(
                columns=[c for c in dropped if c in prices.columns], errors="ignore"
            )
            funding = funding.drop(
                columns=[c for c in dropped if c in funding.columns], errors="ignore"
            )

            # d. Reclassify regime labels with new bull_threshold
            regime["regime"] = "NEUTRAL"
            regime.loc[regime["btc_score"] >= bull_threshold, "regime"] = "BULL"
            regime.loc[regime["btc_score"] <= bt.BEAR_THRESHOLD, "regime"] = "BEAR"

            # e. Monkey-patch BULL_THRESHOLD
            bt.BULL_THRESHOLD = bull_threshold

            # f. Compute alt scores
            alt_scores = bt.compute_alt_scores(
                prices, funding, fees_run, dau_run, equity_rev
            )

            # g. Run backtest
            bt_result = bt.run_backtest(prices, funding, regime, alt_scores)

            # h. Restore BULL_THRESHOLD
            bt.BULL_THRESHOLD = original_bull

            # i. Compute metrics
            metrics = compute_numeric_metrics(bt_result["equity"])

            # j. Store result
            results.append({
                "run_id": run_id,
                "rebalance_day": rebalance_day,
                "bull_threshold": bull_threshold,
                "dropped_assets": dropped_label,
                "sharpe": metrics["sharpe"],
                "max_dd": metrics["max_dd"],
                "ann_return": metrics["ann_return"],
                "final_equity": metrics["final_equity"],
            })

        except Exception as e:
            bt.BULL_THRESHOLD = original_bull
            print(f"  Run {run_id}/{N_RUNS} FAILED: {e}")
            results.append({
                "run_id": run_id,
                "rebalance_day": rebalance_day,
                "bull_threshold": bull_threshold,
                "dropped_assets": dropped_label,
                "sharpe": 0.0,
                "max_dd": 0.0,
                "ann_return": 0.0,
                "final_equity": 0.0,
            })

        # k. Progress
        if run_id % 25 == 0:
            print(f"Run {run_id}/{N_RUNS} complete")

    # 6. Save results CSV
    results_df = pd.DataFrame(results)
    csv_path = OUTPUT_DIR / "monte_carlo_results.csv"
    results_df.to_csv(csv_path, index=False)
    print(f"\nResults saved: {csv_path}")

    # 7. Print summary
    sharpe_values = results_df["sharpe"].dropna()
    n_valid = len(sharpe_values)
    if n_valid > 0:
        sharpe_5th = float(np.percentile(sharpe_values, 5))
        sharpe_50th = float(np.percentile(sharpe_values, 50))
        sharpe_95th = float(np.percentile(sharpe_values, 95))
        pct_above_1_0 = (sharpe_values > 1.0).mean() * 100
        pct_above_0_5 = (sharpe_values > 0.5).mean() * 100

        print(f"\n{'=' * 50}")
        print(f"Monte Carlo Summary ({n_valid} valid runs)")
        print(f"{'=' * 50}")
        print(f"  Sharpe 5th percentile:    {sharpe_5th:.3f}")
        print(f"  Sharpe 50th (median):     {sharpe_50th:.3f}")
        print(f"  Sharpe 95th percentile:   {sharpe_95th:.3f}")
        print(f"  % runs with Sharpe > 1.0: {pct_above_1_0:.1f}%")
        print(f"  % runs with Sharpe > 0.5: {pct_above_0_5:.1f}%")

        # 8. Histogram chart
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.hist(sharpe_values, bins=30, color="steelblue", edgecolor="black", alpha=0.7)
        ax.axvline(
            sharpe_5th, color="red", linestyle="--", linewidth=1.5,
            label=f"5th: {sharpe_5th:.2f}",
        )
        ax.axvline(
            sharpe_50th, color="black", linestyle="--", linewidth=1.5,
            label=f"Median: {sharpe_50th:.2f}",
        )
        ax.axvline(
            sharpe_95th, color="red", linestyle="--", linewidth=1.5,
            label=f"95th: {sharpe_95th:.2f}",
        )
        ax.set_title("Monte Carlo Sharpe Distribution (250 runs)")
        ax.set_xlabel("Sharpe Ratio")
        ax.set_ylabel("Frequency")
        ax.legend()
        ax.grid(True, alpha=0.3)
        fig.tight_layout()

        chart_path = OUTPUT_DIR / "monte_carlo_sharpe_hist.png"
        fig.savefig(chart_path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        print(f"Chart saved: {chart_path}")
    else:
        print("\nNo valid Sharpe ratios to summarize.")

    print("\nDone.")


if __name__ == "__main__":
    main()
