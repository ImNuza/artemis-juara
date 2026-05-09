"""
Transaction Cost Model -- Post-trade cost analysis on strategy backtest
Artemis Quant Competition Track #1 | Deadline: June 1, 2026

Models taker fees + slippage to show the gap between paper and real returns.
"""

import pandas as pd
import numpy as np
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
import backtest as bt

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
RESULTS_DIR = ROOT_DIR / "results" / "integrated"

# ── Constants ────────────────────────────────────────────────────────────────
TAKER_FEE = 0.00035       # 0.035%
INITIAL_CAPITAL = 100_000


# ── Slippage Model ───────────────────────────────────────────────────────────

def slippage_rate(position_notional_usd: float) -> float:
    """Tiered slippage based on position size in USD."""
    if position_notional_usd <= 50_000:
        return 0.0002
    elif position_notional_usd <= 200_000:
        return 0.0005
    else:
        return 0.0010


# ── Cost Calculation Helper ──────────────────────────────────────────────────

def compute_trading_cost_pct(
    equity_multiple: float,
    leverage: float,
    weights: dict,
    initial_capital: float = INITIAL_CAPITAL,
    is_exit_only: bool = False,
) -> float:
    """
    Return the trading cost as a fraction of equity (one period).

    Full round-trip: 2 * leverage * (taker_fee + wavg_slippage)
    Exit-only:       leverage * (taker_fee + wavg_slippage)
    """
    actual_equity = equity_multiple * initial_capital
    total_notional = actual_equity * leverage

    # Weighted-average slippage across positions
    wavg_slippage = 0.0
    for asset, w in weights.items():
        pos_notional = total_notional * w
        wavg_slippage += w * slippage_rate(pos_notional)

    per_side_rate = TAKER_FEE + wavg_slippage

    if is_exit_only:
        cost_pct = leverage * per_side_rate
    else:
        cost_pct = 2.0 * leverage * per_side_rate

    return cost_pct


# ── Backtest With Costs ─────────────────────────────────────────────────────

def run_backtest_with_costs(
    prices: pd.DataFrame,
    funding: pd.DataFrame,
    regime: pd.DataFrame,
    alt_scores: pd.DataFrame,
    initial_capital: float = INITIAL_CAPITAL,
):
    """
    Mirrors bt.run_backtest() but tracks two equity curves.

    * gross_equity  -- no costs (identical to original backtest)
    * net_equity    -- taker fees + slippage deducted

    Returns (gross_df, net_df) -- each a DataFrame with the same columns
    as the original backtest output.
    """
    common_dates = prices.index.intersection(regime.index)
    common_dates = common_dates[common_dates >= bt.START_DATE]

    results_gross = []
    results_net = []
    gross_equity = 1.0
    net_equity = 1.0

    # State for detecting entry/exit transitions
    prev_was_invested = False
    last_weights: dict = {}
    prev_leverage = 0.0

    for i, date in enumerate(common_dates):
        if i == 0:
            init_row = {
                "date": date,
                "equity": 1.0,
                "return": 0.0,
                "regime": "INIT",
                "btc_score": np.nan,
                "leverage": 0.0,
                "positions": "",
                "funding_cost": 0.0,
            }
            results_gross.append(init_row)
            results_net.append(dict(init_row))
            continue

        prev_date = common_dates[i - 1]

        # T-1 regime data
        btc_score = regime.loc[prev_date, "btc_score"]
        prev_regime = regime.loc[prev_date, "regime"]

        # Leverage decision
        if btc_score >= 70:
            leverage = 2.5
        elif btc_score >= bt.BULL_THRESHOLD:
            leverage = 1.5
        else:
            leverage = 0.0

        positions = ""
        port_return = 0.0
        funding_cost = 0.0
        weights: dict = {}

        # ── Position building (mirrors bt.run_backtest exactly) ────────
        if leverage > 0 and prev_regime == "BULL":
            if prev_date in alt_scores.index:
                scores = alt_scores.loc[prev_date].dropna()
                scores = scores[scores > 0]
                investable = scores.drop(
                    [a for a in bt.SHADOW_ASSETS if a in scores.index],
                    errors="ignore",
                )

                if len(investable) >= 1:
                    top = investable.nlargest(min(bt.TOP_N, len(investable)))
                    raw_weights = top / top.sum()

                    weights = raw_weights.copy()
                    capped = weights > bt.MAX_SINGLE_WEIGHT
                    if capped.any():
                        excess = (weights[capped] - bt.MAX_SINGLE_WEIGHT).sum()
                        weights[capped] = bt.MAX_SINGLE_WEIGHT
                        weights[~capped] += excess / (~capped).sum()
                        weights = weights / weights.sum()

                    # Compute weekly return for each position
                    for asset, w in weights.items():
                        if asset in prices.columns:
                            px_prev = prices.loc[prev_date, asset]
                            px_now = prices.loc[date, asset]
                            if pd.notna(px_prev) and pd.notna(px_now) and px_prev > 0:
                                asset_ret = (px_now / px_prev) - 1
                                port_return += w * asset_ret * leverage

                            # Funding cost (signed: positive = pay, negative = receive)
                            if prev_date in funding.index and asset in funding.columns:
                                fr = funding.loc[prev_date, asset]
                                if pd.notna(fr) and fr != 0:
                                    funding_cost += w * leverage * fr

                    positions = ", ".join(
                        f"{a}:{w:.0%}" for a, w in weights.items()
                    )

        # ── Trading cost computation ────────────────────────────────────
        trading_cost = 0.0

        if leverage > 0 and len(weights) > 0:
            # Full round-trip (entry + exit costs) this period
            cost_pct = compute_trading_cost_pct(
                gross_equity,
                leverage,
                weights,
                initial_capital=initial_capital,
                is_exit_only=False,
            )
            trading_cost = cost_pct

        elif prev_was_invested and leverage == 0:
            # Exiting: pay exit-only cost on previous week's weights
            cost_pct = compute_trading_cost_pct(
                gross_equity,
                prev_leverage,
                last_weights,
                initial_capital=initial_capital,
                is_exit_only=True,
            )
            trading_cost = cost_pct

        # ── Update equity curves ────────────────────────────────────────
        gross_equity *= 1.0 + port_return - funding_cost
        net_equity *= 1.0 + port_return - funding_cost - trading_cost

        # ── Track state for next iteration ──────────────────────────────
        prev_was_invested = leverage > 0
        prev_leverage = leverage
        last_weights = dict(weights)

        # ── Build result rows ───────────────────────────────────────────
        gross_row = {
            "date": date,
            "equity": gross_equity,
            "return": port_return - funding_cost,
            "regime": prev_regime,
            "btc_score": btc_score,
            "leverage": leverage,
            "positions": positions,
            "funding_cost": funding_cost,
        }

        net_row = {
            "date": date,
            "equity": net_equity,
            "return": port_return - funding_cost - trading_cost,
            "regime": prev_regime,
            "btc_score": btc_score,
            "leverage": leverage,
            "positions": positions,
            "funding_cost": funding_cost + trading_cost,
        }

        results_gross.append(gross_row)
        results_net.append(net_row)

    gross_df = pd.DataFrame(results_gross).set_index("date")
    net_df = pd.DataFrame(results_net).set_index("date")

    return gross_df, net_df


# ── Metric Parsing & Comparison ─────────────────────────────────────────────

def _parse_metric_value(s) -> float:
    """Convert a formatted metric string (e.g. '25.3%', '1.25x', '1.25') to float."""
    if isinstance(s, str):
        s = s.strip()
        if s.endswith("%"):
            return float(s.rstrip("%")) / 100.0
        elif s.endswith("x"):
            return float(s.rstrip("x"))
        else:
            return float(s)
    return float(s)


def build_comparison(gross_metrics: dict, net_metrics: dict) -> pd.DataFrame:
    """
    Build a comparison DataFrame with columns:
        metric, gross_value, net_value, cost_drag_pct

    * ann_return / max_dd: drag = absolute difference in percentage points
    * sharpe / calmar / final_equity: drag = relative % change
    """
    rows = []

    key_metrics = [
        "Ann. Return",
        "Ann. Volatility",
        "Sharpe Ratio",
        "Max Drawdown",
        "Calmar Ratio",
        "Win Rate",
        "Avg Win",
        "Avg Loss",
        "Profit Factor",
        "Final Equity",
    ]

    for metric in key_metrics:
        if metric not in gross_metrics or metric not in net_metrics:
            continue

        g_val = _parse_metric_value(gross_metrics[metric])
        n_val = _parse_metric_value(net_metrics[metric])

        g_disp = gross_metrics[metric]
        n_disp = net_metrics[metric]

        if metric in ("Ann. Return", "Max Drawdown"):
            # Absolute difference in percentage points
            drag = abs(g_val - n_val) * 100.0
            cost_disp = f"{drag:.1f}pp"
        elif metric in ("Sharpe Ratio", "Calmar Ratio", "Final Equity"):
            # Relative % change
            if abs(g_val) > 1e-12:
                drag = (g_val - n_val) / abs(g_val) * 100.0
            else:
                drag = 0.0
            cost_disp = f"{drag:.1f}%"
        else:
            drag = abs(g_val - n_val)
            cost_disp = f"{drag:.4f}"

        rows.append({
            "metric": metric,
            "gross_value": g_disp,
            "net_value": n_disp,
            "cost_drag_pct": cost_disp,
        })

    return pd.DataFrame(rows)


# ══════════════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════════

def main():
    print("=" * 60)
    print("Transaction Cost Model -- Cost-Adjusted Backtest")
    print("=" * 60)

    # 1. Load data (reuse bt functions)
    print("\n[1/5] Loading data...")
    prices = bt.load_prices(bt.PRICES_PATH)
    funding = bt.load_funding(bt.FUNDING_PATH)
    fees = bt.load_artemis_weekly(bt.FEES_PATH)
    dau = bt.load_artemis_weekly(bt.DAU_PATH)
    equity_rev = bt.load_equity_quarterly(bt.EQUITY_REVENUE_PATH, prices.index)
    btc_price = bt.load_btc_price()
    regime_csv = bt.DATA_DIR / "btc_regime_weekly_optionB.csv"
    regime = bt.load_ImNuza_regime(regime_csv, btc_price)
    alt_scores = bt.compute_alt_scores(prices, funding, fees, dau, equity_rev)
    print(f"  Prices: {prices.shape}, Funding: {funding.shape}, Alt scores: {alt_scores.shape}")

    # 2. Run original backtest as reference
    print("\n[2/5] Running original backtest (reference)...")
    original = bt.run_backtest(prices, funding, regime, alt_scores)
    orig_metrics = bt.compute_metrics(original["equity"])

    # 3. Run backtest with costs
    print("\n[3/5] Running backtest with cost model...")
    gross_df, net_df = run_backtest_with_costs(prices, funding, regime, alt_scores)

    # 4. Validate gross curve matches original
    print("\n[4/5] Validating gross curve against original backtest...")
    gross_metrics = bt.compute_metrics(gross_df["equity"])
    orig_sharpe = _parse_metric_value(orig_metrics["Sharpe Ratio"])
    gross_sharpe = _parse_metric_value(gross_metrics["Sharpe Ratio"])
    sharpe_diff = abs(orig_sharpe - gross_sharpe)

    if sharpe_diff > 0.01:
        print(f"  WARNING: Gross Sharpe ({gross_sharpe:.4f}) differs from "
              f"original ({orig_sharpe:.4f}) by {sharpe_diff:.4f} (> 0.01)")
    else:
        print(f"  Gross Sharpe matches original (diff = {sharpe_diff:.4f}) -- OK")

    # 5. Comparison and output
    print("\n[5/5] Computing cost-adjusted comparison...")
    net_metrics = bt.compute_metrics(net_df["equity"])

    comparison = build_comparison(gross_metrics, net_metrics)
    print("\n--- Cost-Adjusted Comparison ---")
    print(comparison.to_string(index=False))

    output_path = RESULTS_DIR / "cost_adjusted_results.csv"
    comparison.to_csv(output_path, index=False)
    print(f"\nComparison table saved to: {output_path}")

    # Summary line
    orig_sharpe = _parse_metric_value(orig_metrics["Sharpe Ratio"])
    net_sharpe = _parse_metric_value(net_metrics["Sharpe Ratio"])
    cost_drag = (
        (orig_sharpe - net_sharpe) / abs(orig_sharpe) * 100.0
        if abs(orig_sharpe) > 1e-12
        else 0.0
    )
    print(f"\nGross Sharpe: {orig_sharpe:.2f} -> Net Sharpe: {net_sharpe:.2f} "
          f"(cost drag: -{cost_drag:.1f}% annually)")


if __name__ == "__main__":
    main()
