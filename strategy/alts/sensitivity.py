"""
Sensitivity analysis: test BULL thresholds 50, 55, 60, 65
on the full 2022–2026 backtest window.
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
THRESHOLDS = [50, 55, 60, 65]


def run_with_threshold(bull_threshold):
    """Run full backtest with a given BULL threshold (reclassifying regime)."""
    original_bull = bt.BULL_THRESHOLD
    original_bear = bt.BEAR_THRESHOLD
    bt.BULL_THRESHOLD = bull_threshold

    prices = bt.load_prices(bt.PRICES_PATH)
    funding = bt.load_funding(bt.FUNDING_PATH)
    fees = bt.load_artemis_weekly(bt.FEES_PATH)
    dau = bt.load_artemis_weekly(bt.DAU_PATH)
    btc_price = bt.load_btc_price()

    regime_csv = DATA_DIR / "btc_regime_weekly_optionB.csv"
    regime = bt.load_ImNuza_regime(regime_csv, btc_price)

    # Reclassify regime based on THIS threshold (not ImNuza's default >= 60)
    regime["regime"] = "NEUTRAL"
    regime.loc[regime["btc_score"] >= bull_threshold, "regime"] = "BULL"
    regime.loc[regime["btc_score"] <= bt.BEAR_THRESHOLD, "regime"] = "BEAR"

    alt_scores = bt.compute_alt_scores(prices, funding, fees, dau)
    backtest_df = bt.run_backtest(prices, funding, regime, alt_scores)

    metrics = bt.compute_metrics(backtest_df["equity"])

    traded_weeks = (backtest_df["leverage"] > 0).sum()
    total_weeks = len(backtest_df)
    tim = traded_weeks / total_weeks * 100 if total_weeks > 0 else 0

    avg_positions = backtest_df["positions"].apply(
        lambda x: len(x.split(",")) if isinstance(x, str) and x else 0
    ).mean()

    bull_pct = (regime["regime"] == "BULL").mean() * 100

    bt.BULL_THRESHOLD = original_bull  # restore
    return {
        "threshold": bull_threshold,
        "sharpe": float(metrics.get("Sharpe Ratio", 0)),
        "max_dd": metrics.get("Max Drawdown", ""),
        "ann_return": metrics.get("Ann. Return", ""),
        "calmar": float(metrics.get("Calmar Ratio", 0)),
        "final_equity": metrics.get("Final Equity", ""),
        "time_in_market": f"{tim:.0f}%",
        "traded_weeks": f"{traded_weeks}/{total_weeks}",
        "avg_positions": f"{avg_positions:.1f}",
        "regime_bull_pct": f"{bull_pct:.0f}%",
    }


def main():
    print("=" * 70)
    print("BULL Threshold Sensitivity Analysis")
    print("BEAR threshold fixed at <=35 | Window: Jan 2022 – May 2026")
    print("=" * 70)

    results = []
    for t in THRESHOLDS:
        print(f"\nTesting BULL >= {t} ...")
        r = run_with_threshold(t)
        results.append(r)
        print(f"  Sharpe={r['sharpe']:.2f} | DD={r['max_dd']} | "
              f"Equity={r['final_equity']} | InMarket={r['time_in_market']} "
              f"| BULL={r['regime_bull_pct']}")

    # Summary table
    print("\n" + "=" * 70)
    print("Summary Table")
    print("=" * 70)
    df = pd.DataFrame(results)
    print(df.to_string(index=False))

    # Recommendation
    best = max(results, key=lambda x: x["sharpe"])
    print(f"\nHighest Sharpe: BULL >= {best['threshold']} "
          f"(Sharpe {best['sharpe']:.2f}, DD {best['max_dd']}, {best['final_equity']})")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / "sensitivity_results.csv"
    df.to_csv(out_path, index=False)
    print(f"Saved: {out_path}")


if __name__ == "__main__":
    main()
