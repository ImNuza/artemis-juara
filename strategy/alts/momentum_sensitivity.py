"""
Momentum-window sensitivity sweep.

Reruns the integrated backtest at momentum lookbacks {2, 3, 4, 5, 6, 7, 8, 10} weeks.
Captures Sharpe, Max DD, Calmar, Final Equity, Win Rate per window. Output
saved to results/integrated/momentum_sensitivity.csv.

The shipped configuration uses 7 weeks (optimal with Bybit-spliced XMR funding).
"""

import pandas as pd
from pathlib import Path

import backtest as bt


WINDOWS = [2, 3, 4, 5, 6, 7, 8, 10]


def _equity_metrics(equity: pd.Series) -> dict:
    weekly = equity.pct_change().dropna()
    if len(weekly) < 2:
        return {}
    ann_ret = (equity.iloc[-1] / equity.iloc[0]) ** (52.0 / len(weekly)) - 1
    ann_vol = weekly.std() * (52.0 ** 0.5)
    sharpe = ann_ret / ann_vol if ann_vol > 0 else 0.0
    peak = equity.expanding().max()
    dd = (equity - peak) / peak
    max_dd = dd.min()
    calmar = ann_ret / abs(max_dd) if max_dd != 0 else 0.0
    win_rate = (weekly > 0).sum() / len(weekly)
    return {
        "ann_return": round(ann_ret, 4),
        "ann_vol": round(ann_vol, 4),
        "sharpe": round(sharpe, 3),
        "max_dd": round(max_dd, 4),
        "calmar": round(calmar, 3),
        "win_rate": round(win_rate, 4),
        "final_equity": round(equity.iloc[-1], 3),
    }


def main() -> None:
    print("Loading data once...")
    prices    = bt.load_prices(bt.PRICES_PATH)
    funding   = bt.load_funding(bt.FUNDING_PATH)
    fees      = bt.load_artemis_weekly(bt.FEES_PATH)
    dau       = bt.load_artemis_weekly(bt.DAU_PATH)
    equity_rev = bt.load_equity_quarterly(bt.EQUITY_REVENUE_PATH, prices.index)
    btc_price = bt.load_btc_price()
    regime    = bt.load_ImNuza_regime(bt.DATA_DIR / "btc_regime_weekly_optionB.csv", btc_price)

    rows = []
    for w in WINDOWS:
        print(f"\n=== momentum_weeks = {w} ===")
        scores = bt.compute_alt_scores(prices, funding, fees, dau, equity_rev, momentum_weeks=w)
        bt_df  = bt.run_backtest(prices, funding, regime, scores)
        m = _equity_metrics(bt_df["equity"])
        m["momentum_weeks"] = w
        traded = (bt_df["leverage"] > 0).sum()
        m["traded_weeks"] = f"{traded}/{len(bt_df)}"
        rows.append(m)
        print(f"  Sharpe={m['sharpe']:.2f}  MaxDD={m['max_dd']:.1%}  Calmar={m['calmar']:.2f}  Final={m['final_equity']:.2f}x  Traded={m['traded_weeks']}")

    out = pd.DataFrame(rows)[["momentum_weeks", "sharpe", "ann_return", "ann_vol",
                              "max_dd", "calmar", "win_rate", "final_equity", "traded_weeks"]]
    out_path = bt.RESULTS_DIR / "momentum_sensitivity.csv"
    out.to_csv(out_path, index=False)
    print(f"\nSaved: {out_path}")
    print("\nSummary:")
    print(out.to_string(index=False))


if __name__ == "__main__":
    main()
