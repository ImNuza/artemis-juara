"""
Factor attribution: remove each of the 4 active factors one at a time,
re-run the full backtest, and measure marginal Sharpe contribution.
"""
import pandas as pd
import numpy as np
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import backtest as bt

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT_DIR / "data" / "alts"
RESULTS_DIR = ROOT_DIR / "results" / "integrated"


def run_without_factor(excluded_factor):
    """Run backtest with one factor removed, return metrics."""
    # Backup original weights
    original_weights = bt.FACTOR_WEIGHTS.copy()

    # Zero out the excluded factor
    modified = {k: (0.0 if k == excluded_factor else v) for k, v in original_weights.items()}
    bt.FACTOR_WEIGHTS = modified

    prices = bt.load_prices(bt.PRICES_PATH)
    funding = bt.load_funding(bt.FUNDING_PATH)
    fees = bt.load_artemis_weekly(bt.FEES_PATH)
    dau = bt.load_artemis_weekly(bt.DAU_PATH)
    btc_price = bt.load_btc_price()
    equity_rev = bt.load_equity_quarterly(bt.EQUITY_REVENUE_PATH, prices.index)

    regime_csv = DATA_DIR / "btc_regime_weekly_optionB.csv"
    regime = bt.load_ImNuza_regime(regime_csv, btc_price)

    alt_scores = bt.compute_alt_scores(prices, funding, fees, dau, equity_rev)
    backtest_df = bt.run_backtest(prices, funding, regime, alt_scores)

    metrics = bt.compute_metrics(backtest_df["equity"])
    traded_weeks = (backtest_df["leverage"] > 0).sum()
    total_weeks = len(backtest_df)

    bt.FACTOR_WEIGHTS = original_weights  # restore
    return {
        "excluded": excluded_factor,
        "sharpe": float(metrics.get("Sharpe Ratio", 0)),
        "max_dd": metrics.get("Max Drawdown", ""),
        "ann_return": metrics.get("Ann. Return", ""),
        "final_equity": metrics.get("Final Equity", ""),
        "calmar": float(metrics.get("Calmar Ratio", 0)),
        "time_in_market": f"{traded_weeks/total_weeks*100:.0f}%" if total_weeks > 0 else "0%",
    }


def main():
    print("=" * 70)
    print("Factor Attribution Analysis")
    print("Measures marginal Sharpe contribution of each factor")
    print("=" * 70)

    # Baseline (all factors active)
    print("\nRunning baseline (all factors active)...")
    baseline = run_without_factor("__none__")
    baseline["excluded"] = "none (baseline)"
    base_sharpe = baseline["sharpe"]
    base_equity = baseline["final_equity"]
    print(f"  Baseline: Sharpe={base_sharpe:.2f}, DD={baseline['max_dd']}, "
          f"Equity={base_equity}, InMarket={baseline['time_in_market']}")

    results = [baseline]

    active_factors = ["funding_rate", "price_momentum"]
    for f in active_factors:
        print(f"\nRunning without: {f} ...")
        r = run_without_factor(f)
        results.append(r)
        delta = r["sharpe"] - base_sharpe
        print(f"  Sharpe={r['sharpe']:.2f} (delta={delta:+.2f}), DD={r['max_dd']}, "
              f"Equity={r['final_equity']}")

    # Summary
    print("\n" + "=" * 70)
    print("Attribution Summary (Sharpe Delta vs. Baseline)")
    print("=" * 70)

    df = pd.DataFrame(results)
    df["sharpe_delta"] = df["sharpe"] - base_sharpe
    # Sort by negative impact (largest drop = most important)
    df = df.sort_values("sharpe_delta", ascending=True)
    print(df.to_string(index=False))

    print(f"\nBaseline Sharpe: {base_sharpe:.2f}")
    print("\nFactor importance (by Sharpe impact):")
    for _, row in df.iterrows():
        if row["excluded"] == "none (baseline)":
            continue
        impact = row["sharpe_delta"]
        direction = "removes" if impact < 0 else "adds"
        print(f"  {row['excluded']:<20s}: {direction} {abs(impact):.2f} Sharpe")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / "factor_attribution_results.csv"
    df.to_csv(out_path, index=False)
    print(f"\nSaved: {out_path}")


if __name__ == "__main__":
    main()
