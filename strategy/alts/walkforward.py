"""
Walkforward validation: optimise BULL threshold on train window (2022–2023),
evaluate on test window (2024–2026), then report both periods.
"""
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import backtest as bt

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT_DIR / "data" / "alts"
RESULTS_DIR = ROOT_DIR / "results" / "integrated"
TRAIN_START = "2022-01-01"
TRAIN_END = "2023-12-31"
TEST_START = "2024-01-01"
CANDIDATE_THRESHOLDS = [50, 55, 60, 65, 70]
WEEKS_PER_YEAR = 52.0


# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════

def reclassify_regime(regime_raw, bull_threshold):
    """Reclassify regime based on a custom BULL threshold (BEAR uses bt.BEAR_THRESHOLD)."""
    regime = regime_raw.copy()
    regime["regime"] = "NEUTRAL"
    regime.loc[regime["btc_score"] >= bull_threshold, "regime"] = "BULL"
    regime.loc[regime["btc_score"] <= bt.BEAR_THRESHOLD, "regime"] = "BEAR"
    return regime


def _parse_metric(val):
    """Strip % and x suffixes from metric strings, return a float."""
    if isinstance(val, str):
        val = val.strip()
        if val.endswith("%"):
            return float(val[:-1])
        if val.endswith("x"):
            return float(val[:-1])
        return float(val)
    return float(val)


def _time_in_market(backtest_df):
    """Fraction of weeks with nonzero leverage, as a percentage."""
    traded = (backtest_df["leverage"] > 0).sum()
    total = len(backtest_df)
    return traded / total * 100 if total > 0 else 0.0


def _extract_metrics(metrics_dict):
    """Pull sharpe / max_dd / ann_return / final_equity from a compute_metrics dict."""
    if not metrics_dict:
        return {"sharpe": 0.0, "max_dd": 0.0, "ann_return": 0.0, "final_equity": 1.0}
    return {
        "sharpe": _parse_metric(metrics_dict.get("Sharpe Ratio", "0")),
        "max_dd": _parse_metric(metrics_dict.get("Max Drawdown", "0%")),
        "ann_return": _parse_metric(metrics_dict.get("Ann. Return", "0%")),
        "final_equity": _parse_metric(metrics_dict.get("Final Equity", "1.00x")),
    }


# ══════════════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════════

def main():
    print("=" * 60)
    print("Walkforward Validation -- BULL Threshold Optimisation")
    print("=" * 60)

    # ── 1. Load all data (once) ─────────────────────────────────────────────
    print("\n[1/5] Loading data...")
    prices = bt.load_prices(bt.PRICES_PATH)
    funding = bt.load_funding(bt.FUNDING_PATH)
    fees = bt.load_artemis_weekly(bt.FEES_PATH)
    dau = bt.load_artemis_weekly(bt.DAU_PATH)
    equity_rev = bt.load_equity_quarterly(bt.EQUITY_REVENUE_PATH, prices.index)
    btc_price = bt.load_btc_price()
    regime_raw = bt.load_ImNuza_regime(
        DATA_DIR / "btc_regime_weekly_optionB.csv", btc_price
    )
    print(f"  Prices: {len(prices)} weeks, {list(prices.columns)}")
    print(f"  Funding: {len(funding)} weeks")
    print(f"  Regime raw: {len(regime_raw)} weeks")

    # ── 2. Compute alt scores (once) ────────────────────────────────────────
    print("\n[2/5] Computing alt scores...")
    alt_scores = bt.compute_alt_scores(prices, funding, fees, dau, equity_rev)
    print(f"  Alt scores: {len(alt_scores)} weeks ({alt_scores.index[0].date()} to {alt_scores.index[-1].date()})")

    # ── 3. Threshold optimisation loop ──────────────────────────────────────
    print(f"\n[3/5] Optimising BULL threshold on train window "
          f"({TRAIN_START} to {TRAIN_END})...")

    grid_results = []
    best_threshold = CANDIDATE_THRESHOLDS[0]
    best_sharpe = -999.0
    zero_bull_all = True

    for t in CANDIDATE_THRESHOLDS:
        # Save and set global BULL_THRESHOLD (used inside run_backtest for leverage)
        orig_bull = bt.BULL_THRESHOLD
        bt.BULL_THRESHOLD = t

        # Reclassify regime using the current threshold
        regime_t = reclassify_regime(regime_raw, t)

        # Run full backtest
        backtest_t = bt.run_backtest(prices, funding, regime_t, alt_scores)

        # Restore original threshold
        bt.BULL_THRESHOLD = orig_bull

        # Slice train window
        train_equity = backtest_t["equity"].loc[:TRAIN_END]

        # Compute metrics
        metrics = bt.compute_metrics(train_equity)

        # Parse Sharpe (treat empty dict as zero)
        if not metrics:
            sharpe = 0.0
        else:
            sharpe = float(metrics.get("Sharpe Ratio", 0))

        # Time in market on train window
        train_slice = backtest_t.loc[:TRAIN_END]
        tim = _time_in_market(train_slice)

        # Count BULL weeks in train
        train_regime_slice = regime_t.loc[:TRAIN_END]
        bull_weeks = (train_regime_slice["regime"] == "BULL").sum()
        if bull_weeks > 0:
            zero_bull_all = False

        parsed = _extract_metrics(metrics)
        grid_results.append({
            "threshold": t,
            "sharpe": parsed["sharpe"],
            "max_dd": parsed["max_dd"],
            "ann_return": parsed["ann_return"],
            "final_equity": parsed["final_equity"],
            "time_in_market": round(tim, 1),
        })

        print(f"  BULL >= {t:2d}  Sharpe={sharpe:.2f}  "
              f"AnnRet={parsed['ann_return']:.1f}%  "
              f"DD={parsed['max_dd']:.1f}%  "
              f"Equity={parsed['final_equity']:.2f}x  "
              f"InMarket={tim:.0f}%  "
              f"BULLweeks={bull_weeks}")

        if sharpe > best_sharpe:
            best_sharpe = sharpe
            best_threshold = t

    # Edge case: all Sharpe <= 0 or zero BULL weeks across the board
    if best_sharpe <= 0 or zero_bull_all:
        print(f"\n  WARNING: {'zero BULL weeks in train window' if zero_bull_all else 'all Sharpe <= 0'}."
              f" Falling back to threshold 50.")
        best_threshold = 50
        best_sharpe = 0.0

    print(f"\n  >> Best threshold: BULL >= {best_threshold} (train Sharpe = {best_sharpe:.2f})")

    # ── 4. Final run with best threshold ────────────────────────────────────
    print(f"\n[4/5] Running final backtest (BULL >= {best_threshold})...")

    orig_bull = bt.BULL_THRESHOLD
    bt.BULL_THRESHOLD = best_threshold

    regime_final = reclassify_regime(regime_raw, best_threshold)
    backtest_final = bt.run_backtest(prices, funding, regime_final, alt_scores)

    bt.BULL_THRESHOLD = orig_bull

    # Split into train / test
    train_eq = backtest_final["equity"].loc[:TRAIN_END]
    test_eq = backtest_final["equity"].loc[TEST_START:]

    train_parsed = _extract_metrics(bt.compute_metrics(train_eq))
    test_parsed = _extract_metrics(bt.compute_metrics(test_eq))

    train_tim = _time_in_market(backtest_final.loc[:TRAIN_END])
    test_tim  = _time_in_market(backtest_final.loc[TEST_START:])

    print(f"  Train ({TRAIN_START} to {TRAIN_END}):  "
          f"Sharpe={train_parsed['sharpe']:.2f}  "
          f"Ret={train_parsed['ann_return']:.1f}%  "
          f"DD={train_parsed['max_dd']:.1f}%  "
          f"Equity={train_parsed['final_equity']:.2f}x  "
          f"InMarket={train_tim:.0f}%")
    test_end_date = test_eq.index[-1].strftime("%Y-%m-%d")
    print(f"  Test  ({TEST_START} to {test_end_date}):  "
          f"Sharpe={test_parsed['sharpe']:.2f}  "
          f"Ret={test_parsed['ann_return']:.1f}%  "
          f"DD={test_parsed['max_dd']:.1f}%  "
          f"Equity={test_parsed['final_equity']:.2f}x  "
          f"InMarket={test_tim:.0f}%")

    # ── 5. Output CSVs ──────────────────────────────────────────────────────
    print("\n[5/5] Saving outputs...")

    # walkforward_results.csv  (2 rows: train, test)
    results_rows = [
        {
            "window": "train",
            "sharpe": train_parsed["sharpe"],
            "max_dd": train_parsed["max_dd"],
            "ann_return": train_parsed["ann_return"],
            "final_equity": train_parsed["final_equity"],
            "optimal_threshold": best_threshold,
            "time_in_market": round(train_tim, 1),
        },
        {
            "window": "test",
            "sharpe": test_parsed["sharpe"],
            "max_dd": test_parsed["max_dd"],
            "ann_return": test_parsed["ann_return"],
            "final_equity": test_parsed["final_equity"],
            "optimal_threshold": best_threshold,
            "time_in_market": round(test_tim, 1),
        },
    ]
    results_df = pd.DataFrame(results_rows)
    results_df.to_csv(str(RESULTS_DIR / "walkforward_results.csv"), index=False)
    print("  Saved: walkforward_results.csv")

    # walkforward_grid.csv  (5 rows, one per candidate)
    grid_df = pd.DataFrame(grid_results)
    grid_df.to_csv(str(RESULTS_DIR / "walkforward_grid.csv"), index=False)
    print("  Saved: walkforward_grid.csv")

    # ── 6. Chart ────────────────────────────────────────────────────────────
    chart_path = str(RESULTS_DIR / "walkforward_equity.png")
    print(f"\n  Generating: {chart_path}")

    fig, ax = plt.subplots(figsize=(10, 6))

    # Normalise both curves to start at 1.0
    train_norm = train_eq / train_eq.iloc[0]
    test_norm  = test_eq / test_eq.iloc[0]

    ax.plot(train_norm.index, train_norm, label="Train (2022–2023)",
            color="blue", linewidth=1.5)
    ax.plot(test_norm.index, test_norm, label="Test (2024–2026)",
            color="orange", linewidth=1.5)
    ax.axhline(y=1.0, color="gray", linestyle="--", linewidth=0.8)

    ax.set_title(f"Walkforward Validation (best BULL >= {best_threshold})")
    ax.set_ylabel("Equity (multiple)")
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.1fx"))
    ax.legend()
    ax.grid(True, alpha=0.3)

    fig.tight_layout()
    fig.savefig(chart_path, dpi=150, bbox_inches="tight")
    print(f"  Saved: {chart_path}")

    # ── Done ────────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("Walkforward validation complete.")
    print("=" * 60)

    return best_threshold, train_parsed, test_parsed


if __name__ == "__main__":
    main()
