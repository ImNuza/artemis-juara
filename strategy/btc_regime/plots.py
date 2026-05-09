"""Visualization helpers for the BTC regime timeline."""

from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd


REGIME_COLORS = {
    "BULL": "#16a34a",
    "BEAR": "#dc2626",
    "NEUTRAL": "#facc15",
}


def plot_regime_timeline(diag: pd.DataFrame, weekly: pd.DataFrame,
                         output_path: Path,
                         start_date: str = "2022-01-01",
                         title: str = "BTC Composite Valuation Score and Regime Timeline") -> None:
    """Three-panel chart: BTC price, composite score, regime bar."""
    diag = diag.loc[start_date:]
    weekly = weekly.copy()
    weekly["date"] = pd.to_datetime(weekly["date"])
    weekly = weekly.set_index("date").loc[start_date:]

    fig, axes = plt.subplots(
        3, 1, figsize=(15, 11),
        gridspec_kw={"height_ratios": [3, 2, 0.6]},
        sharex=True,
    )

    ax_price = axes[0]
    ax_price.plot(diag.index, diag["input_price"], color="#1f2937", linewidth=1.4, label="BTC price")
    ax_price.set_ylabel("BTC price (USD)")
    ax_price.set_yscale("log")
    ax_price.set_title(title, fontsize=14, fontweight="bold")
    ax_price.legend(loc="upper left")
    ax_price.grid(True, alpha=0.3)

    for regime, color in REGIME_COLORS.items():
        mask = diag["regime"] == regime
        ax_price.fill_between(diag.index, diag["input_price"].min(),
                              diag["input_price"].max(),
                              where=mask, color=color, alpha=0.06,
                              transform=ax_price.get_xaxis_transform()
                              if False else None)

    ax_score = axes[1]
    ax_score.plot(diag.index, diag["btc_score_lagged"], color="#2563eb",
                  linewidth=1.6, label="Composite score (T-1 lagged)")
    ax_score.axhline(60, color="#16a34a", linestyle="--", linewidth=1, alpha=0.7,
                     label="BULL threshold (60)")
    ax_score.axhline(35, color="#dc2626", linestyle="--", linewidth=1, alpha=0.7,
                     label="BEAR threshold (35)")
    ax_score.fill_between(diag.index, 60, 100, alpha=0.06, color="#16a34a")
    ax_score.fill_between(diag.index, 0, 35, alpha=0.06, color="#dc2626")
    ax_score.fill_between(diag.index, 35, 60, alpha=0.06, color="#facc15")
    ax_score.set_ylim(0, 100)
    ax_score.set_ylabel("Composite score (0-100)")
    ax_score.legend(loc="upper left", fontsize=9)
    ax_score.grid(True, alpha=0.3)

    ax_regime = axes[2]
    diag_w = diag.resample("W-MON").last()
    for ts in diag_w.index:
        regime = diag_w.loc[ts, "regime"]
        if pd.isna(regime) or regime == "NA":
            continue
        color = REGIME_COLORS.get(regime, "#9ca3af")
        ax_regime.axvspan(ts - pd.Timedelta(days=3.5),
                          ts + pd.Timedelta(days=3.5),
                          ymin=0, ymax=1, color=color, alpha=0.85)
    ax_regime.set_yticks([])
    ax_regime.set_ylabel("Regime")
    ax_regime.set_xlabel("")

    legend_handles = [
        plt.Rectangle((0, 0), 1, 1, color=c, alpha=0.85, label=r)
        for r, c in REGIME_COLORS.items()
    ]
    ax_regime.legend(handles=legend_handles, loc="upper right", fontsize=8, ncol=3)

    for ax in axes:
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=4))

    plt.setp(axes[-1].xaxis.get_majorticklabels(), rotation=45, ha="right")
    plt.tight_layout()
    plt.savefig(output_path, dpi=140, bbox_inches="tight")
    plt.close(fig)


def plot_subindicator_breakdown(diag: pd.DataFrame, output_path: Path,
                                start_date: str = "2022-01-01") -> None:
    """Stacked normalized sub-indicator panel for diagnostic / report use."""
    diag = diag.loc[start_date:]
    norm_cols = [c for c in diag.columns if c.startswith("norm_")]

    labels = {
        "norm_mvrv_z": "MVRV Z-Score (25%)",
        "norm_puell": "Puell Multiple (20%)",
        "norm_etf_7d": "ETF Inflows 7d (20%)",
        "norm_price_200w_ratio": "200W MA Band (15%)",
        "norm_stable_30d": "Stablecoin Supply Δ 30d (10%)",
        "norm_dom_proxy_30d_roc": "BTC/ETH Dominance ROC inv. (10%)",
    }

    fig, axes = plt.subplots(len(norm_cols), 1, figsize=(15, 13), sharex=True)
    for ax, col in zip(axes, norm_cols):
        s = pd.to_numeric(diag[col], errors="coerce").astype(float)
        ax.plot(s.index, s.values, color="#2563eb", linewidth=1.2)
        ax.fill_between(s.index, 0, s.values, color="#2563eb", alpha=0.12)
        ax.axhline(60, color="#16a34a", linestyle="--", alpha=0.5, linewidth=0.8)
        ax.axhline(35, color="#dc2626", linestyle="--", alpha=0.5, linewidth=0.8)
        ax.set_ylabel(labels.get(col, col), fontsize=9)
        ax.set_ylim(0, 100)
        ax.grid(True, alpha=0.3)

    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    axes[-1].xaxis.set_major_locator(mdates.MonthLocator(interval=4))
    plt.setp(axes[-1].xaxis.get_majorticklabels(), rotation=45, ha="right")

    fig.suptitle("BTC Composite: 6 Sub-Indicators (Normalized 0-100)",
                 fontsize=13, fontweight="bold", y=1.005)
    plt.tight_layout()
    plt.savefig(output_path, dpi=140, bbox_inches="tight")
    plt.close(fig)
