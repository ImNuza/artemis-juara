"""
Systematic optimization: momentum window × threshold (with regime reclassification) × factor weights.
Uses Bybit-spliced XMR funding + phantom-only gate (HYPE, CRCL).
"""

import sys, itertools, json
from pathlib import Path
import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import backtest as bt


def reclassify_regime(regime_raw, bull_threshold):
    """Reclassify regime based on custom threshold (BEAR uses bt.BEAR_THRESHOLD)."""
    regime = regime_raw.copy()
    regime["regime"] = "NEUTRAL"
    regime.loc[regime["btc_score"] >= bull_threshold, "regime"] = "BULL"
    regime.loc[regime["btc_score"] <= bt.BEAR_THRESHOLD, "regime"] = "BEAR"
    return regime


def parse_metric(val):
    if isinstance(val, str):
        val = val.strip()
        if val.endswith("%") or val.endswith("x"):
            return float(val[:-1])
        return float(val)
    return float(val)


def run_config(momentum_weeks, bull_threshold, factor_weights, prices, funding, regime_raw,
               fees, dau, equity_rev):
    """Run backtest with given config, returning key metrics."""
    # Set globals
    orig_mom = bt.MOMENTUM_WEEKS
    orig_bull = bt.BULL_THRESHOLD
    orig_fw = dict(bt.FACTOR_WEIGHTS)

    bt.MOMENTUM_WEEKS = momentum_weeks
    bt.BULL_THRESHOLD = bull_threshold
    bt.FACTOR_WEIGHTS.update(factor_weights)

    try:
        alt_scores = bt.compute_alt_scores(prices, funding, fees, dau, equity_rev)
        regime_t = reclassify_regime(regime_raw, bull_threshold)
        backtest = bt.run_backtest(prices, funding, regime_t, alt_scores)
        metrics = bt.compute_metrics(backtest["equity"])
    finally:
        bt.MOMENTUM_WEEKS = orig_mom
        bt.BULL_THRESHOLD = orig_bull
        bt.FACTOR_WEIGHTS.update(orig_fw)

    if not metrics:
        return None

    equity = parse_metric(metrics.get("Final Equity", "1.00x"))
    sharpe = parse_metric(metrics.get("Sharpe Ratio", "0"))
    max_dd = parse_metric(metrics.get("Max Drawdown", "0%"))
    ann_ret = parse_metric(metrics.get("Ann. Return", "0%"))
    calmar = parse_metric(metrics.get("Calmar Ratio", "0"))
    traded = (backtest["leverage"] > 0).sum()
    bull_weeks = (regime_t["regime"] == "BULL").sum()
    total_weeks = len(backtest)

    return {
        "momentum_weeks": momentum_weeks,
        "bull_threshold": bull_threshold,
        "funding_w": factor_weights.get("funding_rate", 0.55),
        "momentum_w": factor_weights.get("price_momentum", 0.45),
        "sharpe": round(sharpe, 4),
        "max_dd": round(max_dd, 2),
        "ann_return": round(ann_ret, 2),
        "equity": round(equity, 2),
        "calmar": round(calmar, 4),
        "traded_weeks": int(traded),
        "bull_weeks": int(bull_weeks),
        "time_in_market": round(traded / total_weeks * 100, 1) if total_weeks > 0 else 0,
    }


def main():
    print("Loading data...")
    prices = bt.load_prices(bt.PRICES_PATH)
    funding = bt.load_funding(bt.FUNDING_PATH)
    fees = bt.load_artemis_weekly(bt.FEES_PATH)
    dau = bt.load_artemis_weekly(bt.DAU_PATH)
    equity_rev = bt.load_equity_quarterly(bt.EQUITY_REVENUE_PATH, prices.index)
    btc_price = bt.load_btc_price()
    regime_raw = bt.load_ImNuza_regime(bt.DATA_DIR / "btc_regime_weekly_optionB.csv", btc_price)
    print(f"  Prices: {len(prices)}w, Funding: {len(funding)}w, Regime: {len(regime_raw)}w")

    momentum_windows = [3, 4, 5, 6, 7, 8, 10]
    thresholds = [50, 55, 60, 65]
    factor_configs = [
        {"funding_rate": 0.55, "price_momentum": 0.45},
        {"funding_rate": 0.60, "price_momentum": 0.40},
        {"funding_rate": 0.50, "price_momentum": 0.50},
        {"funding_rate": 0.45, "price_momentum": 0.55},
    ]

    total = len(momentum_windows) * len(thresholds) * len(factor_configs)
    print(f"Testing {total} configurations ({len(momentum_windows)} mom × {len(thresholds)} thresh × {len(factor_configs)} weights)...\n")

    results = []
    for i, (mw, th, fw) in enumerate(itertools.product(momentum_windows, thresholds, factor_configs)):
        r = run_config(mw, th, fw, prices, funding, regime_raw, fees, dau, equity_rev)
        if r:
            results.append(r)
        if (i + 1) % 20 == 0 or i == total - 1:
            print(f"  [{i+1}/{total}] done...")

    # Sort by Sharpe descending
    results.sort(key=lambda r: r["sharpe"], reverse=True)

    print(f"\n{'='*95}")
    print("TOP 20 CONFIGURATIONS (by Sharpe)")
    print(f"{'='*95}")
    print(f"{'#':>3} {'MomW':>5} {'Thr':>4} {'FW':>5} {'MW':>5} {'Sharpe':>7} {'DD':>7} {'Ret':>7} {'Eq':>7} {'Calmar':>7} {'BULLw':>6} {'Traded':>6} {'TiM':>5}")
    print("-" * 95)
    for i, r in enumerate(results[:20]):
        print(f"{i+1:>3} {r['momentum_weeks']:>5} {r['bull_threshold']:>4} "
              f"{r['funding_w']:.2f} {r['momentum_w']:.2f} "
              f"{r['sharpe']:>7.2f} {r['max_dd']:>6.1f}% {r['ann_return']:>6.1f}% "
              f"{r['equity']:>6.2f}x {r['calmar']:>7.2f} {r['bull_weeks']:>6} {r['traded_weeks']:>6} {r['time_in_market']:>4.0f}%")

    # Best by Calmar
    by_calmar = sorted(results, key=lambda r: r["calmar"], reverse=True)
    print(f"\n{'='*95}")
    print("TOP 10 BY CALMAR")
    print(f"{'='*95}")
    for i, r in enumerate(by_calmar[:10]):
        print(f"{i+1:>3} {r['momentum_weeks']:>5} {r['bull_threshold']:>4} "
              f"{r['funding_w']:.2f} {r['momentum_w']:.2f} "
              f"{r['sharpe']:>7.2f} {r['max_dd']:>6.1f}% {r['ann_return']:>6.1f}% "
              f"{r['equity']:>6.2f}x {r['calmar']:>7.2f} {r['bull_weeks']:>6} {r['traded_weeks']:>6} {r['time_in_market']:>4.0f}%")

    # Summary: best Sharpe per momentum window
    print(f"\n{'='*95}")
    print("BEST SHARPE PER MOMENTUM WINDOW")
    print(f"{'='*95}")
    for mw in momentum_windows:
        subset = [r for r in results if r["momentum_weeks"] == mw]
        if subset:
            best = max(subset, key=lambda r: r["sharpe"])
            print(f"  {mw:>2}w: Sharpe {best['sharpe']:.2f} | Thr={best['bull_threshold']} "
                  f"FW={best['funding_w']:.2f} MW={best['momentum_w']:.2f} | "
                  f"DD={best['max_dd']:.1f}% Ret={best['ann_return']:.1f}% "
                  f"Eq={best['equity']:.2f}x Calmar={best['calmar']:.2f} | "
                  f"BULL={best['bull_weeks']}w Traded={best['traded_weeks']}w")

    # Summary: best Sharpe per threshold
    print(f"\n{'='*95}")
    print("BEST SHARPE PER THRESHOLD")
    print(f"{'='*95}")
    for th in thresholds:
        subset = [r for r in results if r["bull_threshold"] == th]
        if subset:
            best = max(subset, key=lambda r: r["sharpe"])
            print(f"  {th:>2}: Sharpe {best['sharpe']:.2f} | Mom={best['momentum_weeks']}w "
                  f"FW={best['funding_w']:.2f} MW={best['momentum_w']:.2f} | "
                  f"DD={best['max_dd']:.1f}% Ret={best['ann_return']:.1f}% "
                  f"Eq={best['equity']:.2f}x Calmar={best['calmar']:.2f} | "
                  f"BULL={best['bull_weeks']}w Traded={best['traded_weeks']}w")

    # Best overall
    best = results[0]
    print(f"\n{'='*95}")
    print("BEST OVERALL CONFIGURATION")
    print(f"{'='*95}")
    print(f"  Momentum: {best['momentum_weeks']}w | Threshold: {best['bull_threshold']} | "
          f"Funding: {best['funding_w']:.0%} | Momentum: {best['momentum_w']:.0%}")
    print(f"  Sharpe: {best['sharpe']:.2f} | DD: {best['max_dd']:.1f}% | "
          f"Ann Ret: {best['ann_return']:.1f}% | Equity: {best['equity']:.2f}x | "
          f"Calmar: {best['calmar']:.2f}")
    print(f"  BULL weeks: {best['bull_weeks']} | Traded: {best['traded_weeks']} | "
          f"Time in market: {best['time_in_market']:.0f}%")

    # Save full results
    out_path = bt.RESULTS_DIR / "optimization_sweep.csv"
    pd.DataFrame(results).to_csv(str(out_path), index=False)
    print(f"\nFull results saved to {out_path}")


if __name__ == "__main__":
    main()
