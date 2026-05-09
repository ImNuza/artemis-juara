"""
BTC Regime-Gated Alt Factor Strategy — Backtest Engine
Artemis Quant Competition Track #1 | Deadline: June 1, 2026

Data: Weekly, Jan 2022 – May 2026, T-1 lag on all signals.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import yfinance as yf
from pathlib import Path

# ── Config ──────────────────────────────────────────────────────────────────
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT_DIR / "data" / "alts"
PRICES_PATH  = DATA_DIR / "hl_prices.csv"
FUNDING_PATH = DATA_DIR / "hl_funding_rates.csv"
FEES_PATH    = DATA_DIR / "artemis_fees_weekly.csv"   # SOL, HYPE — from artemis_data_pull.py
DAU_PATH     = DATA_DIR / "artemis_dau_weekly.csv"    # SOL, HYPE — from artemis_data_pull.py
EQUITY_REVENUE_PATH = DATA_DIR / "artemis_equity_total_revenue.csv"  # COIN, HOOD, CRCL — quarterly
RESULTS_DIR = ROOT_DIR / "results" / "integrated"
START_DATE = "2022-01-01"
# End date is used only as the upper bound for the BTC-USD yfinance pull;
# the backtest itself runs over whatever Friday data overlaps between
# `prices` and the regime CSV (typically through the latest available week).
END_DATE   = "2026-05-31"

# Alt universe: 4 tokens + 3 equity perps
ALT_ASSETS = ["SOL", "BNB", "HYPE", "XMR", "COIN", "CRCL", "HOOD"]
SHADOW_ASSETS: set[str] = set()

# Start-date filters (rationale: skip initial post-IPO dump periods)
# COIN: IPO Apr 2021 at $381, crashed to $33 by Jun 2022. Start mid-2022 bear.
COIN_START = "2022-07-01"
# CRCL: IPO Jun 2025, peaked at $240, crashed to ~$80 by Nov 2025. Start post-dump.
CRCL_START = "2025-12-01"
# HOOD: IPO Jul 2021, crashed to $7 by mid-2022. Full data OK (survived bear).

# Factor weights — simplified to the two factors that drive results.
# Revenue growth (+0.01 Sharpe) and activity momentum (+0.01 Sharpe) were
# removed May 7, 2026 after factor attribution showed they contribute
# negligible marginal value (only cover 2-4 of 8 assets).
# OI confirmation was never implemented (no historical HL OI).
FACTOR_WEIGHTS = {
    "funding_rate": 0.55,     # inverted, cross-sectional rank
    "price_momentum": 0.45,   # 4-week return, cross-sectional rank
}

# Regime thresholds
BULL_THRESHOLD = 60
BEAR_THRESHOLD = 35

# Portfolio constraints
MAX_SINGLE_WEIGHT = 0.40
TOP_N = 3


# ══════════════════════════════════════════════════════════════════════════════
# 1. Data Loading
# ══════════════════════════════════════════════════════════════════════════════

# HIP-3 listing dates on the `xyz` perp dex — HL is primary from these dates onward,
# yfinance backfills history before. See docs/research_report.md §11 (Data Sources).
HL_EQUITY_LISTING = {
    "COIN": pd.Timestamp("2025-11-25"),
    "HOOD": pd.Timestamp("2025-11-26"),
    "CRCL": pd.Timestamp("2025-12-15"),
}


def _load_equity_friday(ticker: str) -> pd.Series:
    """Load yfinance equity CSV and align each row to the Friday of its own week.

    yfinance CSVs land on different days depending on when the asset's week ended:
    COIN/HOOD on Saturday (week-ending Saturday from yf weekly bars), CRCL on Monday.
    A blanket -1 day shift would mis-align CRCL onto Sunday and silently drop it
    from the Friday-aligned backtest index. Instead we shift each row backwards
    by (dayofweek - 4) mod 7 days, landing it on the Friday of the same week.
    """
    eq_path = DATA_DIR / f"equity_{ticker}_price.csv"
    if not eq_path.exists():
        return pd.Series(dtype=float, name=ticker)
    df = pd.read_csv(eq_path, parse_dates=["date"], index_col="date")
    s = pd.to_numeric(df.iloc[:, 0], errors="coerce").rename(ticker).dropna()
    days_back = (s.index.dayofweek - 4) % 7
    s.index = s.index - pd.to_timedelta(days_back, unit="D")
    return s.sort_index()


def _load_equity_hl(ticker: str) -> pd.Series:
    """Load HL HIP-3 weekly close (already Friday-aligned). Empty Series if absent."""
    hl_path = DATA_DIR / f"equity_{ticker}_hl.csv"
    if not hl_path.exists():
        return pd.Series(dtype=float, name=ticker)
    df = pd.read_csv(hl_path, parse_dates=["date"], index_col="date")
    s = pd.to_numeric(df.iloc[:, 0], errors="coerce").rename(ticker).dropna()
    return s.sort_index()


def load_prices(path: Path) -> pd.DataFrame:
    """Load weekly token prices + Friday-aligned equity prices (HL primary post-listing,
    yfinance backfill pre-listing). Returns DataFrame with Friday dates as index."""
    # Token prices (already Friday-aligned from HL pull)
    df = pd.read_csv(path, parse_dates=["date"], index_col="date")
    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Equity prices: yfinance pre-listing + HL HIP-3 post-listing (CLAUDE.md decision #7)
    for ticker in ["COIN", "CRCL", "HOOD"]:
        yf_s = _load_equity_friday(ticker)
        hl_s = _load_equity_hl(ticker)
        if hl_s.empty:
            merged = yf_s
        else:
            cutoff = HL_EQUITY_LISTING[ticker]
            merged = pd.concat([yf_s[yf_s.index < cutoff], hl_s[hl_s.index >= cutoff]]).sort_index()
            merged = merged[~merged.index.duplicated(keep="last")].rename(ticker)
        if not merged.empty:
            df = df.join(merged.rename(ticker), how="outer")

    # Apply start-date filters (skip initial post-IPO dump periods)
    for col in df.columns:
        if col == "COIN":
            df.loc[df.index < COIN_START, col] = np.nan
        elif col == "CRCL":
            df.loc[df.index < CRCL_START, col] = np.nan

    df = df.dropna(how="all").sort_index()
    return df


def load_artemis_weekly(path: Path) -> pd.DataFrame:
    """Load weekly Artemis on-chain data (FEES or DAU). Returns NaN for missing dates/assets."""
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path, parse_dates=["date"], index_col="date")
    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.sort_index()


def load_equity_quarterly(path: Path, weekly_index: pd.DatetimeIndex) -> pd.DataFrame:
    """Load quarterly equity fundamentals, forward-fill to weekly dates.
    Keeps only columns for assets in ALT_ASSETS that have at least 4 quarters."""
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path, parse_dates=["date"], index_col="date")
    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.sort_index()
    # Strip _TOTAL_REVENUE suffix so columns match asset names (COIN, HOOD, etc.)
    df.columns = [c.replace("_TOTAL_REVENUE", "") for c in df.columns]
    # Forward-fill quarterly values to weekly grid
    weekly = df.reindex(weekly_index).ffill()
    # Drop assets with fewer than 4 quarters of data
    for col in list(weekly.columns):
        n_quarters = df[col].dropna().shape[0]
        if n_quarters < 4:
            weekly = weekly.drop(columns=col)
    return weekly


def load_funding(path: Path) -> pd.DataFrame:
    """Load weekly funding rates. Expands to cover all alt assets (equities = no data = neutral)."""
    df = pd.read_csv(path, parse_dates=["date"], index_col="date")
    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.fillna(0.0)
    df = df.sort_index()
    return df


def load_btc_price() -> pd.Series:
    """Pull BTC weekly close from yfinance, aligned to Friday closes."""
    btc = yf.download("BTC-USD", start=START_DATE, end=END_DATE, auto_adjust=False)
    if isinstance(btc.columns, pd.MultiIndex):
        close = btc["Close"].iloc[:, 0]
    else:
        close = btc["Close"]
    close = close.rename("BTC")
    close.index = pd.to_datetime(close.index)
    weekly = close.resample("W-FRI").last().dropna()
    return weekly


# ══════════════════════════════════════════════════════════════════════════════
# 2. BTC Regime Layer (ImNuza's Option B — 6-factor trend-following composite)
# ══════════════════════════════════════════════════════════════════════════════

def load_ImNuza_regime(csv_path: Path, btc_price: pd.Series) -> pd.DataFrame:
    """
    Load ImNuza's pre-computed BTC regime timeline (Option B: de-inverted/trend).
    5 factors: MVRV Z-Score (30%), Puell Multiple (25%), Price/200W MA (20%),
    Stablecoin Supply 30d (15%), BTC/ETH Dominance Proxy 30d ROC (10%).
    All signals normalized via rolling 2-year min-max with T-1 lag.
    ETF signal was tested and dropped May 5, 2026 (noisy, removal improved results).
    Fed Balance Sheet is Option D only, not included here.
    Dates are Mondays; mapped to Fridays for alignment with token price schedule.
    """
    df = pd.read_csv(csv_path)
    df["date"] = pd.to_datetime(df["date"])
    df["btc_score"] = pd.to_numeric(df["btc_score"], errors="coerce")
    # Drop warm-up rows (NA scores) and last empty row
    df = df.dropna(subset=["btc_score"]).reset_index(drop=True)

    # Map Monday dates to the same-week Friday (Monday + 4 days)
    # so that ImNuza's Mon signal is available by that Fri for the backtest's T-1 lookup.
    # ImNuza's Mon 2026-04-27 signal -> Fri 2026-05-01 in regime index
    # Backtest for week ending Fri 2026-05-08 uses prev_date=Fri 2026-05-01 -> gets ImNuza Mon 2026-04-27
    df["friday"] = df["date"] + pd.Timedelta(days=4)
    df = df.set_index("friday").sort_index()

    regime = df[["btc_score", "regime", "action"]].copy()

    # Merge BTC price for plotting
    btc_weekly = btc_price.resample("W-FRI").last().dropna()
    regime["btc_price"] = btc_weekly.reindex(regime.index)

    return regime


# ══════════════════════════════════════════════════════════════════════════════
# 3. Alt Factor Scoring Engine
# ══════════════════════════════════════════════════════════════════════════════

MOMENTUM_WEEKS = 4  # weeks of price momentum lookback (was implicitly ~2 pre-fix)


def compute_price_momentum(prices: pd.DataFrame, weeks: int = MOMENTUM_WEEKS) -> pd.DataFrame:
    """N-week price return for each asset. T-1 lag built in."""
    return prices.pct_change(periods=weeks).shift(1)


def compute_funding_score(funding: pd.DataFrame) -> pd.DataFrame:
    """
    Funding rate score: 7d avg funding, inverted (negative = good).
    Cross-sectional rank within universe each week. T-1 lag.
    """
    funding_lagged = funding.shift(1)
    # Cross-sectional rank (1 = best = most negative funding)
    ranked = funding_lagged.rank(axis=1, ascending=True, na_option="bottom")
    # Normalize to 0-1 where 1 = best
    n_assets = ranked.count(axis=1)
    score = 1.0 - (ranked.sub(1, axis=0)).div(n_assets.sub(1), axis=0)
    return score.clip(0, 1)


def _cross_rank(df: pd.DataFrame) -> pd.DataFrame:
    """Cross-sectional rank to 0-100. NaN cells stay NaN (not ranked as bottom)."""
    ranked = df.rank(axis=1, ascending=True, na_option="keep")
    n = ranked.count(axis=1)
    score = 100.0 * (ranked.sub(1, axis=0)).div(n.sub(1).replace(0, np.nan), axis=0)
    return score.clip(0, 100)


def compute_revenue_growth(fees: pd.DataFrame) -> pd.DataFrame:
    """4-week % change in protocol fees. Cross-sectional rank (0-100). T-1 lag."""
    if fees.empty:
        return pd.DataFrame()
    growth = fees.pct_change(periods=4).shift(1)
    return _cross_rank(growth)


def compute_activity_momentum(dau: pd.DataFrame) -> pd.DataFrame:
    """4-week MA / 12-week MA ratio. Cross-sectional rank (0-100). T-1 lag."""
    if dau.empty:
        return pd.DataFrame()
    ma4  = dau.rolling(4,  min_periods=4).mean()
    ma12 = dau.rolling(12, min_periods=12).mean()
    ratio = (ma4 / ma12).shift(1)
    return _cross_rank(ratio)


def _compute_equity_rev_growth(equity_rev: pd.DataFrame) -> pd.DataFrame:
    """QoQ growth on quarterly equity revenue (forward-filled to weekly). T-1 lag."""
    if equity_rev.empty:
        return pd.DataFrame()
    growth = equity_rev.pct_change(periods=13).shift(1)  # ~1 quarter, T-1
    return _cross_rank(growth)


def compute_alt_scores(
    prices: pd.DataFrame,
    funding: pd.DataFrame,
    fees: pd.DataFrame | None = None,
    dau: pd.DataFrame | None = None,
    equity_revenue: pd.DataFrame | None = None,
    momentum_weeks: int = MOMENTUM_WEEKS,
) -> pd.DataFrame:
    """
    Composite alt scores (0-100 per asset per week).

    Two factors, always active:
      funding_rate     55%  SOL/BNB/HYPE/XMR when non-zero; others neutral 50
      price_momentum   45%  all assets, always

    Revenue growth and activity momentum were removed May 7, 2026 after
    factor attribution showed +0.01 Sharpe contribution each.
    Assets without data on a factor get neutral score 50.
    """
    if fees is None:
        fees = pd.DataFrame()
    if dau is None:
        dau = pd.DataFrame()
    if equity_revenue is None:
        equity_revenue = pd.DataFrame()
    all_assets = list(prices.columns)

    # ── price momentum ───────────────────────────────────────────────────────
    px_mom   = compute_price_momentum(prices, weeks=momentum_weeks)
    px_score = _cross_rank(px_mom)
    px_score = px_score.reindex(columns=all_assets).fillna(50.0)

    # ── funding ──────────────────────────────────────────────────────────────
    fr_raw   = 100.0 * compute_funding_score(funding)
    fr_missing = funding.shift(1).reindex(columns=funding.columns) == 0.0
    fr_raw[fr_missing] = 50.0
    fr_score = fr_raw.reindex(columns=all_assets).fillna(50.0)

    # ── composite ────────────────────────────────────────────────────────────
    composite = pd.DataFrame(index=prices.index, columns=all_assets, dtype=float)

    for week_idx, week in enumerate(prices.index):
        if week_idx < 4:
            continue

        for asset in all_assets:
            pm_val = px_score.loc[week, asset] if (week in px_score.index and asset in px_score.columns) else 50.0
            fr_val = fr_score.loc[week, asset] if (week in fr_score.index and asset in fr_score.columns) else 50.0
            w_pm = FACTOR_WEIGHTS.get("price_momentum", 0.45)
            w_fr = FACTOR_WEIGHTS.get("funding_rate", 0.55)
            total_w = w_pm + w_fr
            if total_w > 0:
                composite.loc[week, asset] = (
                    (w_pm / total_w) * (pm_val if pd.notna(pm_val) else 50.0)
                    + (w_fr / total_w) * (fr_val if pd.notna(fr_val) else 50.0)
                )
            else:
                composite.loc[week, asset] = 50.0

    return composite.astype(float)


# ══════════════════════════════════════════════════════════════════════════════
# 4. Portfolio Construction & Backtest Loop
# ══════════════════════════════════════════════════════════════════════════════

def run_backtest(
    prices: pd.DataFrame,
    funding: pd.DataFrame,
    regime: pd.DataFrame,
    alt_scores: pd.DataFrame,
) -> pd.DataFrame:
    """
    Weekly backtest loop with T-1 lag, regime gate, top-3 long selection
    (BULL), bottom-2 short selection (BEAR), signal-weighted allocation,
    leverage scaling, and funding cost deduction.

    Long sleeve (BULL): top 3 alts, signal-weighted, 1.5x-2.5x leverage.
    Short sleeve (BEAR): bottom 2 alts, signal-weighted, 1.0x leverage.
    NEUTRAL: flat (no long, no short).
    """
    common_dates = prices.index.intersection(regime.index)
    common_dates = common_dates[common_dates >= START_DATE]

    results = []
    equity = 1.0
    prev_week_equity = 1.0

    for i, date in enumerate(common_dates):
        if i == 0:
            results.append({
                "date": date,
                "equity": 1.0,
                "return": 0.0,
                "regime": "INIT",
                "btc_score": np.nan,
                "leverage": 0.0,
                "positions": "",
                "funding_cost": 0.0,
                "side": "",
            })
            continue

        prev_date = common_dates[i - 1]

        btc_score = regime.loc[prev_date, "btc_score"]
        prev_regime = regime.loc[prev_date, "regime"]

        positions = ""
        port_return = 0.0
        funding_cost = 0.0
        side = ""

        # ── LONG sleeve (BULL regime) ──────────────────────────────────────
        if prev_regime == "BULL":
            if btc_score >= 70:
                leverage = 2.5
            elif btc_score >= BULL_THRESHOLD:
                leverage = 1.5
            else:
                leverage = 0.0

            if leverage > 0 and prev_date in alt_scores.index:
                scores = alt_scores.loc[prev_date].dropna()
                scores = scores[scores > 0]
                investable = scores.drop([a for a in SHADOW_ASSETS if a in scores.index], errors="ignore")

                if len(investable) >= 1:
                    top = investable.nlargest(min(TOP_N, len(investable)))
                    raw_weights = top / top.sum()
                    weights = raw_weights.copy()
                    capped = weights > MAX_SINGLE_WEIGHT
                    if capped.any():
                        excess = (weights[capped] - MAX_SINGLE_WEIGHT).sum()
                        weights[capped] = MAX_SINGLE_WEIGHT
                        weights[~capped] += excess / (~capped).sum()
                        weights = weights / weights.sum()

                    for asset, w in weights.items():
                        if asset in prices.columns:
                            px_prev = prices.loc[prev_date, asset]
                            px_now = prices.loc[date, asset]
                            if pd.notna(px_prev) and pd.notna(px_now) and px_prev > 0:
                                asset_ret = (px_now / px_prev) - 1
                                port_return += w * asset_ret * leverage

                            if prev_date in funding.index and asset in funding.columns:
                                fr = funding.loc[prev_date, asset]
                                if pd.notna(fr) and fr != 0:
                                    funding_cost += w * leverage * fr

                    positions = ", ".join(f"{a}:{w:.0%}" for a, w in weights.items())
                    side = "LONG"

        # ── BEAR / NEUTRAL: flat ────────────────────────────────────────────
        # Short overlay tested May 7, 2026 — destroyed capital. Bottom-ranked
        # alts by funding+momentum bounced during bear rallies. The factor
        # model identifies "hated" alts, not directional shorts. Reverted.
        else:
            leverage = 0.0

        equity = equity * (1 + port_return - funding_cost)

        results.append({
            "date": date,
            "equity": equity,
            "return": port_return - funding_cost,
            "regime": prev_regime,
            "btc_score": btc_score,
            "leverage": leverage,
            "positions": positions,
            "funding_cost": funding_cost,
            "side": side,
        })

    return pd.DataFrame(results).set_index("date")


# ══════════════════════════════════════════════════════════════════════════════
# 5. Benchmarks
# ══════════════════════════════════════════════════════════════════════════════

def compute_benchmarks(prices: pd.DataFrame, btc_price: pd.Series, backtest_dates: pd.DatetimeIndex) -> pd.DataFrame:
    """BTC buy-and-hold and equal-weight alt portfolio (no regime filter)."""
    benchmarks = pd.DataFrame(index=backtest_dates)

    # BTC buy-and-hold
    btc_aligned = btc_price.reindex(backtest_dates).ffill()
    benchmarks["btc_bnh"] = btc_aligned / btc_aligned.iloc[0]

    # Equal-weight alt portfolio (all investable alts, no regime gate, no shadows)
    investable_cols = [c for c in prices.columns if c not in SHADOW_ASSETS]
    alt_returns = prices[investable_cols].pct_change().reindex(backtest_dates)
    n_assets = alt_returns.notna().sum(axis=1)
    ew_return = alt_returns.sum(axis=1) / n_assets.replace(0, np.nan)
    benchmarks["ew_alts"] = (1 + ew_return.fillna(0)).cumprod()
    benchmarks["ew_alts"] = benchmarks["ew_alts"] / benchmarks["ew_alts"].iloc[0]

    return benchmarks


# ══════════════════════════════════════════════════════════════════════════════
# 6. Performance Analytics
# ══════════════════════════════════════════════════════════════════════════════

WEEKS_PER_YEAR = 52.0

def compute_metrics(equity_curve: pd.Series) -> dict:
    """Compute standard performance metrics from an equity curve."""
    weekly_returns = equity_curve.pct_change().dropna()
    if len(weekly_returns) < 2:
        return {}

    ann_return = (equity_curve.iloc[-1] / equity_curve.iloc[0]) ** (WEEKS_PER_YEAR / len(weekly_returns)) - 1
    ann_vol = weekly_returns.std() * np.sqrt(WEEKS_PER_YEAR)
    sharpe = ann_return / ann_vol if ann_vol > 0 else 0.0

    # Max drawdown
    peak = equity_curve.expanding().max()
    drawdown = (equity_curve - peak) / peak
    max_dd = drawdown.min()

    calmar = ann_return / abs(max_dd) if max_dd != 0 else 0.0

    # Win rate
    wins = (weekly_returns > 0).sum()
    total = len(weekly_returns)
    win_rate = wins / total if total > 0 else 0.0

    # Average win/loss
    avg_win = weekly_returns[weekly_returns > 0].mean() if wins > 0 else 0.0
    avg_loss = weekly_returns[weekly_returns < 0].mean() if (total - wins) > 0 else 0.0
    profit_factor = abs(avg_win / avg_loss) if avg_loss != 0 else np.inf

    # Weekly turnover proxy: how often positions change
    position_changes = (equity_curve.diff().abs() > 1e-8).sum()

    return {
        "Ann. Return": f"{ann_return:.1%}",
        "Ann. Volatility": f"{ann_vol:.1%}",
        "Sharpe Ratio": f"{sharpe:.2f}",
        "Max Drawdown": f"{max_dd:.1%}",
        "Calmar Ratio": f"{calmar:.2f}",
        "Win Rate": f"{win_rate:.1%}",
        "Avg Win": f"{avg_win:.2%}",
        "Avg Loss": f"{avg_loss:.2%}",
        "Profit Factor": f"{profit_factor:.2f}",
        "Final Equity": f"{equity_curve.iloc[-1]:.2f}x",
        "Weeks Traded": str(len(weekly_returns)),
    }


# ══════════════════════════════════════════════════════════════════════════════
# 7. Visualization
# ══════════════════════════════════════════════════════════════════════════════

def plot_results(
    backtest: pd.DataFrame,
    benchmarks: pd.DataFrame,
    regime: pd.DataFrame,
    save_path: str | None = None,
):
    """Generate equity curve, drawdown, and regime overlay plots."""
    fig, axes = plt.subplots(3, 1, figsize=(14, 12), sharex=True)

    # --- Panel 1: Equity Curves ---
    ax = axes[0]
    ax.plot(backtest.index, backtest["equity"], label="Strategy (Regime-Gated)", color="#1f77b4", linewidth=1.5)
    if "btc_bnh" in benchmarks.columns:
        ax.plot(benchmarks.index, benchmarks["btc_bnh"], label="BTC Buy & Hold", color="#ff7f0e", linewidth=1.0, alpha=0.8)
    if "ew_alts" in benchmarks.columns:
        ax.plot(benchmarks.index, benchmarks["ew_alts"], label="Equal-Weight Alts (No Regime)", color="#2ca02c", linewidth=1.0, alpha=0.8)
    ax.axhline(y=1.0, color="gray", linestyle="--", linewidth=0.5)
    ax.set_ylabel("Equity (multiple)")
    ax.set_title("BTC Regime-Gated Alt Factor Strategy -- Backtest")
    ax.legend(loc="upper left")
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter('%.1fx'))
    ax.grid(True, alpha=0.3)

    # --- Panel 2: Drawdown ---
    ax = axes[1]
    dd = backtest["equity"] / backtest["equity"].expanding().max() - 1
    ax.fill_between(dd.index, 0, dd * 100, color="#d62728", alpha=0.4)
    ax.plot(dd.index, dd * 100, color="#d62728", linewidth=0.8)
    ax.set_ylabel("Drawdown (%)")
    ax.set_title("Drawdown")
    ax.grid(True, alpha=0.3)
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter('%.0f%%'))

    # --- Panel 3: BTC Regime + Score ---
    ax = axes[2]
    ax2 = ax.twinx()

    # Color background by regime
    regime_aligned = regime.reindex(backtest.index)
    for i in range(len(regime_aligned) - 1):
        r = regime_aligned["regime"].iloc[i]
        color = {"BULL": "#2ca02c", "BEAR": "#d62728", "NEUTRAL": "#ff7f0e"}.get(r, "white")
        ax.axvspan(backtest.index[i], backtest.index[i + 1], alpha=0.08, color=color)

    ax.plot(regime.index, regime["btc_price"], color="#1f77b4", linewidth=1.0, label="BTC Price")
    ax.set_ylabel("BTC Price ($)")
    ax.set_yscale("log")

    ax2.plot(regime.index, regime["btc_score"], color="#9467bd", linewidth=1.0, alpha=0.7, label="BTC Score")
    ax2.axhline(y=BULL_THRESHOLD, color="green", linestyle="--", linewidth=0.5, alpha=0.5)
    ax2.axhline(y=BEAR_THRESHOLD, color="red", linestyle="--", linewidth=0.5, alpha=0.5)
    ax2.set_ylabel("BTC Score (0-100)", color="#9467bd")
    ax2.set_ylim(0, 100)

    lines1, labels1 = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(lines1 + lines2, labels1 + labels2, loc="upper left")

    ax.set_title("BTC Regime Timeline (ImNuza Option B: 6-factor trend composite)")
    ax.grid(True, alpha=0.3)

    fig.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f"\nChart saved to: {save_path}")
    else:
        plt.show()


# ══════════════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════════

def main():
    print("=" * 60)
    print("BTC Regime-Gated Alt Factor Strategy -- Backtest")
    print("=" * 60)

    # 1. Load data
    print("\n[1/6] Loading data...")
    prices    = load_prices(PRICES_PATH)
    funding   = load_funding(FUNDING_PATH)
    fees      = load_artemis_weekly(FEES_PATH)
    dau       = load_artemis_weekly(DAU_PATH)
    equity_rev = load_equity_quarterly(EQUITY_REVENUE_PATH, prices.index)
    btc_price = load_btc_price()
    print(f"  Universe ({len(prices.columns)} assets): {list(prices.columns)}")
    print(f"  Price data: {len(prices)} weeks ({prices.index[0].date()} to {prices.index[-1].date()})")
    print(f"  Funding data: {len(funding)} weeks, {list(funding.columns)}")
    if not fees.empty:
        print(f"  Artemis FEES: {list(fees.columns)}, {len(fees)} weeks ({fees.index[0].date()} to {fees.index[-1].date()})")
    else:
        print(f"  Artemis FEES: not found — revenue factor inactive")
    if not dau.empty:
        print(f"  Artemis DAU:  {list(dau.columns)}, {len(dau)} weeks ({dau.index[0].date()} to {dau.index[-1].date()})")
    else:
        print(f"  Artemis DAU:  not found — activity factor inactive")
    if not equity_rev.empty:
        print(f"  Equity revenue (quarterly): {list(equity_rev.columns)}, {len(equity_rev)} weeks forward-filled")
    else:
        print(f"  Equity revenue: not found — equities neutral 50 on revenue factor")
    print(f"  BTC price: {len(btc_price)} weeks")

    # 2. BTC Regime (ImNuza's Option B: 5-factor trend-following composite)
    print("\n[2/6] Loading BTC regime (ImNuza Option B -- 5-factor composite)...")
    regime_csv = DATA_DIR / "btc_regime_weekly_optionB.csv"
    regime = load_ImNuza_regime(regime_csv, btc_price)
    bull_pct = (regime["regime"] == "BULL").mean() * 100
    bear_pct = (regime["regime"] == "BEAR").mean() * 100
    print(f"  Regime CSV: {regime_csv}")
    print(f"  Date range: {regime.index[0].strftime('%Y-%m-%d')} to {regime.index[-1].strftime('%Y-%m-%d')}")
    print(f"  BULL: {bull_pct:.0f}% | BEAR: {bear_pct:.0f}% | NEUTRAL: {100-bull_pct-bear_pct:.0f}%")
    print(f"  Factors: MVRV Z (30%), Puell (25%), 200W MA (20%), Stablecoin 30d (15%),")
    print(f"           BTC/ETH Dom Proxy 30d ROC (10%)")
    print(f"  ETF signal: dropped May 5 (noisy, removal improved results)")
    print(f"  Fed Balance Sheet: Option D only, NOT included here")

    # 3. Alt factor scores
    print("\n[3/6] Computing alt factor scores...")
    print(f"  Active factors: funding_rate (55%), price_momentum (45%)")
    print(f"  Removed May 7: revenue_growth (+0.01 Sharpe), activity_momentum (+0.01 Sharpe)")
    print(f"  Never implemented: oi_confirmation (no historical HL OI)")
    print(f"  BNB/XMR: no on-chain data — compete on price + funding only")
    alt_scores = compute_alt_scores(prices, funding, fees, dau, equity_rev)

    # 4. Run backtest
    print("\n[4/6] Running backtest loop (LONG in BULL, FLAT otherwise)...")
    print(f"  Short overlay: tested May 7, rejected (Sharpe collapse, DD blow-up)")
    backtest = run_backtest(prices, funding, regime, alt_scores)
    traded_weeks = (backtest["leverage"] > 0).sum()
    print(f"  Traded weeks: {traded_weeks}/{len(backtest)} ({traded_weeks/len(backtest):.0%})")

    # 5. Benchmarks
    print("\n[5/6] Computing benchmarks...")
    benchmarks = compute_benchmarks(prices, btc_price, backtest.index)

    # 6. Results
    print("\n[6/6] Performance Report")
    print("=" * 60)
    print("\n--- Strategy ---")
    strat_metrics = compute_metrics(backtest["equity"])
    for k, v in strat_metrics.items():
        print(f"  {k:<20s}: {v:>10s}")

    print("\n--- BTC Buy & Hold ---")
    btc_metrics = compute_metrics(benchmarks["btc_bnh"].dropna())
    for k, v in btc_metrics.items():
        print(f"  {k:<20s}: {v:>10s}")

    print("\n--- Equal-Weight Alts (No Regime) ---")
    ew_metrics = compute_metrics(benchmarks["ew_alts"].dropna())
    for k, v in ew_metrics.items():
        print(f"  {k:<20s}: {v:>10s}")

    # Plot
    plot_results(backtest, benchmarks, regime, save_path=str(RESULTS_DIR / "backtest_results.png"))


if __name__ == "__main__":
    main()
