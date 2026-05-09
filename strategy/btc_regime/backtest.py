"""Quick BTC-only regime backtest.

Strategy: when regime == BULL, hold 100% BTC. When NEUTRAL or BEAR, hold cash (zero return).
This is NOT the final v2 strategy — that uses an alt factor model on top of the regime gate.
This script is just to check whether the regime gate, in isolation, helps or hurts.

Starting capital: $100,000
Rebalance: weekly on Monday
"""

from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .composite import compute_regime_timeline
from .data_loader import load_btc_price


BASE_DIR = Path(__file__).resolve().parents[2]
RESULTS_DIR = BASE_DIR / "results" / "btc_regime"

START_DATE = "2020-01-01"
START_CAPITAL = 100_000.0


def run_regime_backtest(diag: pd.DataFrame, weekly: pd.DataFrame,
                        price: pd.Series, label: str) -> dict:
    """Hold BTC when regime == BULL, cash otherwise. Returns metrics dict."""
    weekly = weekly.copy()
    weekly["date"] = pd.to_datetime(weekly["date"])
    weekly = weekly.set_index("date")

    daily_idx = price.loc[START_DATE:].index
    capital = START_CAPITAL
    btc_position_value = 0.0
    cash = capital
    holdings = []

    weekly_idx = pd.DatetimeIndex(weekly.index)
    rebalance_set = set(weekly_idx)

    last_btc_price = None
    in_btc = False

    for date in daily_idx:
        p = price.loc[date]
        if pd.isna(p):
            holdings.append({"date": date, "value": btc_position_value + cash,
                             "in_btc": in_btc, "regime": None, "btc_price": p})
            continue

        if in_btc and last_btc_price is not None and last_btc_price > 0:
            btc_position_value *= p / last_btc_price

        if date in rebalance_set:
            row = weekly.loc[date] if date in weekly.index else None
            if row is not None and isinstance(row, pd.Series):
                regime = row.get("regime")
            else:
                regime = None

            if regime == "BULL" and not in_btc:
                btc_position_value = cash
                cash = 0.0
                in_btc = True
            elif regime != "BULL" and in_btc:
                cash = btc_position_value
                btc_position_value = 0.0
                in_btc = False

        last_btc_price = p
        holdings.append({"date": date, "value": btc_position_value + cash,
                         "in_btc": in_btc, "regime": locals().get("regime", None),
                         "btc_price": p})

    df = pd.DataFrame(holdings).set_index("date")
    return _compute_metrics(df, label)


def run_buy_hold_btc(price: pd.Series, label: str = "BTC Buy & Hold") -> dict:
    p = price.loc[START_DATE:]
    eq = START_CAPITAL * (p / p.iloc[0])
    df = pd.DataFrame({"value": eq, "btc_price": p})
    return _compute_metrics(df, label)


def _compute_metrics(df: pd.DataFrame, label: str) -> dict:
    eq = df["value"]
    eq = eq.replace(0, np.nan).ffill()
    rets = eq.pct_change().dropna()
    total_days = (eq.index[-1] - eq.index[0]).days
    years = total_days / 365.25
    total_return = eq.iloc[-1] / eq.iloc[0] - 1
    ann_return = (1 + total_return) ** (1 / years) - 1 if years > 0 else 0
    ann_vol = rets.std() * np.sqrt(365)
    sharpe = ann_return / ann_vol if ann_vol > 0 else 0
    rolling_max = eq.cummax()
    drawdown = (eq - rolling_max) / rolling_max
    max_dd = drawdown.min()
    calmar = ann_return / abs(max_dd) if max_dd != 0 else 0
    return {
        "label": label,
        "equity": eq,
        "drawdown": drawdown,
        "final_value": eq.iloc[-1],
        "total_return": total_return,
        "ann_return": ann_return,
        "ann_vol": ann_vol,
        "sharpe": sharpe,
        "max_drawdown": max_dd,
        "calmar": calmar,
    }


def fmt_metrics(m: dict) -> str:
    return (f"{m['label']:<35} "
            f"final=${m['final_value']:>11,.0f}  "
            f"total_ret={m['total_return']:>+8.1%}  "
            f"ann_ret={m['ann_return']:>+7.1%}  "
            f"sharpe={m['sharpe']:>+5.2f}  "
            f"max_dd={m['max_drawdown']:>+7.1%}")


def plot_equity_comparison(metrics_list: list[dict], output_path: Path) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(14, 9),
                             gridspec_kw={"height_ratios": [3, 1]}, sharex=True)
    palette = ["#2563eb", "#16a34a", "#dc2626", "#f59e0b"]
    for i, m in enumerate(metrics_list):
        axes[0].plot(m["equity"].index, m["equity"].values,
                     label=f"{m['label']} (final ${m['final_value']:,.0f})",
                     color=palette[i % len(palette)], linewidth=1.7)
        axes[1].fill_between(m["drawdown"].index, m["drawdown"].values, 0,
                             color=palette[i % len(palette)], alpha=0.25,
                             label=m["label"])
    axes[0].set_ylabel("Portfolio value ($)")
    axes[0].set_yscale("log")
    axes[0].set_title(f"BTC Regime Gate Backtest — $100K starting capital, "
                      f"{START_DATE} to present", fontsize=13, fontweight="bold")
    axes[0].legend(loc="upper left", fontsize=10)
    axes[0].grid(True, alpha=0.3)
    axes[1].set_ylabel("Drawdown")
    axes[1].yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f"{y:.0%}"))
    axes[1].grid(True, alpha=0.3)
    axes[1].legend(loc="lower left", fontsize=8)
    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    axes[-1].xaxis.set_major_locator(mdates.MonthLocator(interval=4))
    plt.setp(axes[-1].xaxis.get_majorticklabels(), rotation=45, ha="right")
    plt.tight_layout()
    plt.savefig(output_path, dpi=140, bbox_inches="tight")
    plt.close(fig)


def main():
    price = load_btc_price()

    print(f"Backtest from {START_DATE}, starting capital ${START_CAPITAL:,.0f}")
    print()

    diag_a, weekly_a = compute_regime_timeline(mode="plan")
    m_a = run_regime_backtest(diag_a, weekly_a, price,
                              label="Option A: Plan (contrarian)")

    diag_b, weekly_b = compute_regime_timeline(mode="trend")
    m_b = run_regime_backtest(diag_b, weekly_b, price,
                              label="Option B: De-inverted (trend)")

    diag_d, weekly_d = compute_regime_timeline(mode="D")
    m_d = run_regime_backtest(diag_d, weekly_d, price,
                              label="Option D: Trend + Fed BS macro")

    m_buyhold = run_buy_hold_btc(price)

    print("=" * 140)
    for m in [m_a, m_b, m_d, m_buyhold]:
        print(fmt_metrics(m))
    print("=" * 140)

    diag_a.to_csv(RESULTS_DIR / "btc_composite_daily_full_optionA.csv")
    weekly_a.to_csv(RESULTS_DIR / "btc_regime_weekly_optionA.csv", index=False)
    diag_b.to_csv(RESULTS_DIR / "btc_composite_daily_full_optionB.csv")
    weekly_b.to_csv(RESULTS_DIR / "btc_regime_weekly_optionB.csv", index=False)
    diag_d.to_csv(RESULTS_DIR / "btc_composite_daily_full_optionD.csv")
    weekly_d.to_csv(RESULTS_DIR / "btc_regime_weekly_optionD.csv", index=False)
    weekly_d.to_csv(RESULTS_DIR / "btc_regime_weekly.csv", index=False)  # default = D

    summary_rows = []
    for m in [m_a, m_b, m_d, m_buyhold]:
        summary_rows.append({
            "strategy": m["label"],
            "final_value_usd": round(m["final_value"], 0),
            "total_return": round(m["total_return"], 4),
            "ann_return": round(m["ann_return"], 4),
            "ann_volatility": round(m["ann_vol"], 4),
            "sharpe": round(m["sharpe"], 3),
            "max_drawdown": round(m["max_drawdown"], 4),
            "calmar": round(m["calmar"], 3),
        })
    pd.DataFrame(summary_rows).to_csv(RESULTS_DIR / "regime_backtest_summary.csv", index=False)

    plot_equity_comparison([m_a, m_b, m_d, m_buyhold],
                           RESULTS_DIR / "regime_backtest_equity.png")

    print()
    print(f"Outputs saved to {RESULTS_DIR}/")
    return m_a, m_b, m_d, m_buyhold


if __name__ == "__main__":
    main()
