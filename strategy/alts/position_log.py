"""
Generate docs/position_log.md from a fresh backtest run.

The backtest stores per-week regime, BTC score, leverage, and positions in the
result DataFrame. This script summarises that into a markdown artifact judges
can read to understand exactly when and how the strategy traded.

Sections produced:
  1. Headline metrics
  2. Regime distribution
  3. Per-asset selection frequency
  4. Year-by-year breakdown
  5. Full position log (every BULL week — every week the strategy actually traded)
  6. Compact regime timeline (BULL/BEAR/NEUTRAL transitions)
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

import pandas as pd
import numpy as np

import backtest as bt


OUT_PATH = Path(__file__).resolve().parent.parent.parent / "docs" / "position_log.md"


def _parse_positions(s: str) -> list[tuple[str, float]]:
    """Parse 'SOL:40%, HYPE:30%' -> [('SOL', 0.40), ('HYPE', 0.30)]."""
    if not s:
        return []
    out = []
    for tok in s.split(","):
        m = re.match(r"\s*([A-Z]+)\s*:\s*(-?\d+(?:\.\d+)?)%\s*$", tok)
        if m:
            out.append((m.group(1), float(m.group(2)) / 100.0))
    return out


def _run_backtest_with_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.Series]:
    prices    = bt.load_prices(bt.PRICES_PATH)
    funding   = bt.load_funding(bt.FUNDING_PATH)
    fees      = bt.load_artemis_weekly(bt.FEES_PATH)
    dau       = bt.load_artemis_weekly(bt.DAU_PATH)
    equity_rev = bt.load_equity_quarterly(bt.EQUITY_REVENUE_PATH, prices.index)
    btc_price = bt.load_btc_price()
    regime    = bt.load_ImNuza_regime(bt.DATA_DIR / "btc_regime_weekly_optionB.csv", btc_price)
    scores    = bt.compute_alt_scores(prices, funding, fees, dau, equity_rev)
    result    = bt.run_backtest(prices, funding, regime, scores)
    return result, prices, btc_price


def _section_headline(result: pd.DataFrame) -> str:
    metrics = bt.compute_metrics(result["equity"])
    traded = (result["leverage"] > 0).sum()
    lines = [
        "## 1. Headline Metrics",
        "",
        f"- **Window:** {result.index[0].date()} → {result.index[-1].date()} ({len(result)} weekly bars)",
        f"- **Sharpe:** {metrics['Sharpe Ratio']}",
        f"- **Max Drawdown:** {metrics['Max Drawdown']}",
        f"- **Final Equity:** {metrics['Final Equity']}",
        f"- **Annualised Return:** {metrics['Ann. Return']}",
        f"- **Time in Market:** {traded}/{len(result)} weeks "
        f"({traded/len(result):.0%})",
        "",
    ]
    return "\n".join(lines)


def _section_regime(result: pd.DataFrame) -> str:
    counts = result["regime"].value_counts(dropna=False)
    total = len(result)
    lines = [
        "## 2. Regime Distribution",
        "",
        "| Regime | Weeks | Share |",
        "|---|---:|---:|",
    ]
    for r in ["BULL", "NEUTRAL", "BEAR", "INIT"]:
        n = int(counts.get(r, 0))
        if n == 0 and r == "INIT":
            continue
        lines.append(f"| {r} | {n} | {n/total:.0%} |")
    lines.append("")
    lines.append("Strategy deploys capital only in BULL. NEUTRAL and BEAR are flat.")
    lines.append("")
    return "\n".join(lines)


def _section_asset_frequency(result: pd.DataFrame) -> str:
    asset_count: Counter[str] = Counter()
    asset_weight: dict[str, float] = {}
    bull_weeks = 0
    for s in result["positions"]:
        parsed = _parse_positions(s)
        if parsed:
            bull_weeks += 1
            for asset, w in parsed:
                asset_count[asset] += 1
                asset_weight[asset] = asset_weight.get(asset, 0.0) + w

    lines = [
        "## 3. Asset Selection Frequency",
        "",
        f"Across **{bull_weeks} weeks** where the strategy was deployed:",
        "",
        "| Asset | Weeks Selected | % of BULL Weeks | Avg Weight When Held |",
        "|---|---:|---:|---:|",
    ]
    universe = ["SOL", "BNB", "HYPE", "XMR", "COIN", "CRCL", "HOOD"]
    for a in universe:
        n = asset_count.get(a, 0)
        share = n / bull_weeks if bull_weeks > 0 else 0.0
        avg_w = (asset_weight.get(a, 0.0) / n) if n > 0 else 0.0
        lines.append(f"| {a} | {n} | {share:.0%} | {avg_w:.0%} |")
    lines.append("")
    return "\n".join(lines)


def _section_year_breakdown(result: pd.DataFrame) -> str:
    rows = []
    prior_end_eq = 1.0  # baseline equity before the first traded year
    for year, group in result.groupby(result.index.year):
        if len(group) == 0:
            continue
        bull_weeks = (group["regime"] == "BULL").sum()
        traded = (group["leverage"] > 0).sum()
        end_eq = group["equity"].iloc[-1]
        # Year-on-year return uses prior year's ending equity as the base,
        # so per-year returns compound exactly to the headline final equity.
        year_return = (end_eq / prior_end_eq) - 1.0
        max_lev = group["leverage"].max()
        rows.append({
            "Year": int(year),
            "Weeks": len(group),
            "BULL weeks": int(bull_weeks),
            "Weeks traded": int(traded),
            "Year return (YoY)": f"{year_return:+.1%}",
            "Max leverage": f"{max_lev:.1f}x",
            "End equity": f"{end_eq:.2f}x",
        })
        prior_end_eq = end_eq
    df = pd.DataFrame(rows)

    lines = [
        "## 4. Year-by-Year Breakdown",
        "",
        "| " + " | ".join(df.columns) + " |",
        "|" + "|".join(["---"] * len(df.columns)) + "|",
    ]
    for _, r in df.iterrows():
        lines.append("| " + " | ".join(str(v) for v in r.values) + " |")
    lines.append("")
    lines.append(
        "*Note:* `Year return (YoY)` is the realised year-on-year equity change "
        "(`End equity / prior year's End equity − 1`), so the yearly returns compound "
        "exactly to the headline final equity. This differs from the strategy's "
        "headline annualised return (geometric CAGR over the full window), which is "
        "reported in §1."
    )
    lines.append("")
    return "\n".join(lines)


def _section_full_log(result: pd.DataFrame) -> str:
    lines = [
        "## 5. Full Position Log (Every BULL Week)",
        "",
        "These are all the weeks the strategy actually had capital deployed. "
        "Each row is a single weekly rebalance: the regime/score is the **previous** "
        "week's value (T-1 lag), the leverage is selected by that BTC score, and the "
        "positions are signal-weighted top-3 alts capped at 40% per asset.",
        "",
        "| Week | BTC Score | Leverage | Positions | Weekly Return | Equity After |",
        "|---|---:|---:|---|---:|---:|",
    ]
    bull_rows = result[result["leverage"] > 0]
    for d, row in bull_rows.iterrows():
        ret_pct = row["return"] * 100
        lines.append(
            f"| {d.date()} | {row['btc_score']:.0f} | {row['leverage']:.1f}x | "
            f"{row['positions']} | {ret_pct:+.2f}% | {row['equity']:.3f}x |"
        )
    lines.append("")
    return "\n".join(lines)


def _section_timeline(result: pd.DataFrame) -> str:
    """Compact regime timeline — collapses runs of the same regime."""
    runs = []
    cur_regime = None
    cur_start = None
    for d, row in result.iterrows():
        r = row["regime"]
        if r != cur_regime:
            if cur_regime is not None:
                runs.append((cur_regime, cur_start, prev_d))
            cur_regime = r
            cur_start = d
        prev_d = d
    if cur_regime is not None:
        runs.append((cur_regime, cur_start, prev_d))

    lines = [
        "## 6. Compact Regime Timeline",
        "",
        "Consecutive weeks of the same regime, collapsed:",
        "",
        "| Regime | Start | End | Weeks |",
        "|---|---|---|---:|",
    ]
    for r, s, e in runs:
        n = ((e - s).days // 7) + 1
        lines.append(f"| {r} | {s.date()} | {e.date()} | {n} |")
    lines.append("")
    return "\n".join(lines)


def _header(result: pd.DataFrame) -> str:
    return (
        "# Position Log — BTC Regime-Gated Alt Factor Strategy\n\n"
        "Auto-generated from the integrated backtest (`strategy/alts/backtest.py`). "
        "Re-run `python strategy/alts/position_log.py` to refresh.\n\n"
        "**Note:** BTC is the regime gate signal only — it is never held as a position. "
        "The strategy trades alt perps on Hyperliquid; BTC price and on-chain data "
        "determine whether the strategy is deployed (BULL) or flat (BEAR/NEUTRAL).\n\n"
        f"_Window: {result.index[0].date()} → {result.index[-1].date()}._\n\n"
        "---\n\n"
    )


def main() -> None:
    print("Running backtest...")
    result, _prices, _btc = _run_backtest_with_data()

    print(f"Writing {OUT_PATH}...")
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    parts = [
        _header(result),
        _section_headline(result),
        _section_regime(result),
        _section_asset_frequency(result),
        _section_year_breakdown(result),
        _section_full_log(result),
        _section_timeline(result),
    ]
    OUT_PATH.write_text("\n".join(parts), encoding="utf-8")
    print(f"Saved {OUT_PATH} ({OUT_PATH.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
