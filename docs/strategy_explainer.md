# BTC Regime-Gated Alt Factor Strategy -- Explainer

**Team:** ImNuza (BTC regime gate) + Xynerss (alt factor engine)
**Venue:** Artemis Analytics Competition 2026, Track #1
**Deadline:** June 1, 2026

---

## 1. Strategy Overview (One Paragraph)

We run a long-only altcoin/equity-perp portfolio on Hyperliquid that only deploys capital when Bitcoin's macro regime is bullish. The regime gate is a 5-factor composite score (ImNuza). When the gate is open (BULL), we rank 7 assets by a 2-factor cross-sectional score (Xynerss), take the top 3, size them by signal strength with a 40% single-asset cap, and apply 1.5x-2.5x leverage depending on conviction. When the gate is closed (BEAR), we sit flat in USDC. The result: we get alt beta in bull markets and avoid the -64% drawdowns that come from being long during bear markets. We post Sharpe 1.31, drawdown -27.2%, final equity 5.63x. Net of costs: Sharpe 1.27, 5.33x.

---

## 2. Why Two Layers?

Altcoins are levered bets on Bitcoin. When BTC trends down, alts get crushed regardless of their individual fundamentals. A pure cross-sectional ranking of alts (Layer 2 alone) would still hold positions through bear markets and suffer catastrophic drawdowns.

**Layer 1 (BTC Regime Gate)** answers: *should we be in the market at all?*
**Layer 2 (Alt Factor Engine)** answers: *if yes, which alts do we hold?*

This layering means the strategy only takes risk when the macro environment is favorable. The regime gate is not a subtle timing signal; it's a blunt on/off switch, and that's intentional.

---

## 3. Layer 1: BTC Regime Gate (ImNuza)

### 3.1 The Composite Score

Five factors (Option B), each normalized via rolling 2-year min-max, combined with fixed weights:

| Factor | Weight | Source | What It Measures |
|--------|--------|--------|------------------|
| MVRV Z-Score | 30% | CoinMetrics | On-chain valuation extreme |
| Puell Multiple | 25% | BTC miner revenue / 365d MA | Miner profitability cycle |
| Price vs 200W MA Ratio | 20% | Artemis | Structural trend |
| Stablecoin Supply Δ 30d | 15% | Artemis | Crypto-native liquidity |
| BTC/ETH Dominance 30d ROC | 10% | Artemis | Risk appetite (BTC vs ETH) |

Each factor is scored 0 to 100 and combined into `BTC_Score`. The ETF Inflows signal (originally 20%) was dropped May 5, 2026 after testing showed it added noise; Fed Balance Sheet appears only in Option D, not the shipped Option B.

### 3.2 Regime Classification

```
BTC_Score ≥ 60  →  BULL     →  Deploy alt portfolio
BTC_Score ≤ 35  →  BEAR     →  Exit entirely, sit in USDC
35 < BTC_Score < 60 → NEUTRAL →  Flat in USDC, no positions
```

### 3.3 Why These Thresholds?

The thresholds (60/35) were chosen by ImNuza and **validated** by sensitivity analysis. Testing BULL thresholds from 50 to 65 on the full 2022 to 2026 backtest window:

| Threshold | Sharpe | Max DD | Result |
|-----------|--------|--------|--------|
| 50 | 1.42 | -33.1% | Too loose; admits weaker signals, larger DD |
| 55 | 1.46 | -35.1% | Highest raw Sharpe but DD widens |
| **60** | **1.31** | **-27.2%** | **Shipped: best Sharpe-vs-DD tradeoff** |
| 65 | 0.83 | -28.1% | Too tight; misses real bull runs |

Threshold 55 produces a higher raw Sharpe (1.46 vs 1.31) but at -35.1% drawdown vs -27.2%. We ship 60 (ImNuza's pre-classified value) because the lower drawdown matters more than the small Sharpe gain for a strategy positioned around risk control.

### 3.4 Regime Split (2018 to 2026)

| Regime | Weeks | % |
|--------|-------|---|
| BULL | 76 | 18.5% |
| NEUTRAL | 145 | 35.4% |
| BEAR | 189 | 46.1% |

The strategy is only actively deploying ~19% of the time. This low time-in-market is a feature, not a bug; it means the strategy is patient.

---

## 4. Layer 2: Alt Factor Engine (Xynerss)

### 4.1 Universe

7 assets on Hyperliquid Perps:

| Asset | Category | Price Data | On-Chain Data |
|-------|----------|------------|---------------|
| SOL | L1 token | Since Jan 2022 | Fees + DAU (Artemis) |
| HYPE | DEX token | Since Dec 2024 | Fees + DAU (Artemis) |
| BNB | CEX token | Since Jan 2022 | None (Artemis limitation) |
| XMR | Privacy coin | Since Apr 2023 | None (by design) |
| COIN | CEX equity | Since Jul 2022 | N/A |
| HOOD | CEX equity | Since Jan 2022 | N/A |
| CRCL | Stablecoin equity | Since Dec 2025 | N/A |

Equity perps (COIN, HOOD, CRCL) carry real funding rate data from their HIP-3 listing dates (Nov-Dec 2025) via `pull_hl_equities.py`. Pre-listing: they get neutral-50 on the funding factor. Post-listing: they participate in the cross-sectional funding rank normally. No BULL weeks have occurred since the equity listing dates (BTC regime has been BEAR/NEUTRAL from Nov 2025 to present), so this has zero backtest impact; it's a correctness fix for future data.

### 4.2 The Two Factors

Revenue growth and activity momentum were removed May 7, 2026 after factor attribution showed they each contributed +0.01 Sharpe (negligible value). They only had data for 2 of 7 assets (SOL and HYPE). The remaining two factors account for the full signal:

| Factor | Weight | Signal | Available For |
|--------|--------|--------|---------------|
| Funding Rate (inverted) | 45% | Weekly HL funding, Bybit-spliced pre-HL for SOL/BNB (before May 2023) and XMR (before 2026-01-16); HIP-3 funding for equities from listing. Negative = bullish. | All 7 assets where data exists |
| Price Momentum | 55% | 7-week return, cross-sectional rank | All 7 assets |

OI Confirmation (10%) was planned but blocked -- Hyperliquid has no historical OI time series.

### 4.3 Scoring

Assets without funding data get neutral score 50 for that factor (no benefit, no penalty). Both factors are always active, so there is no per-week weight redistribution. The composite is simply:

```
Alt_Score = 0.45 * funding_score + 0.55 * momentum_score
```

### 4.4 Anti-Lookahead Rules (Non-Negotiable)

- **T-1 lag:** All signals use the previous week's data. You cannot trade on Friday's close using Friday's data.
- **Rolling 2-year min-max normalization:** Scores are normalized against the trailing 2-year window, not the full sample. No peeking at future highs/lows.
- **Data available after:** Equities must have 12 weeks of price history before entering the universe.

### 4.5 Portfolio Construction (BULL weeks only)

1. Rank all 7 assets by composite Alt_Score
2. Select top 3 (fewer if less than 3 have scores)
3. Weight by signal strength: `weight_i = score_i / sum(top 3 scores)`
4. Cap any single asset at 40%
5. Apply leverage:
   - BTC_Score ≥ 70 → 2.5x
   - BTC_Score 60 to 70 → 1.5x
   - Otherwise → 0x (flat)

Equity perps on COIN, CRCL, and HOOD get neutral 50 for on-chain factors (revenue, DAU). They compete purely on price momentum and funding rate, same as BNB and XMR. This is documented as an expected limitation, not a bug.

---

## 5. Backtest Results (Jan 2022 -- May 2026)

| Metric | Strategy | BTC B&H | EW Alts (No Regime) |
|--------|----------|---------|---------------------|
| Ann. Return | **48.8%** | 16.3% | 40.7% |
| Ann. Volatility | 37.3% | 51.3% | 50.2% |
| Sharpe Ratio | **1.31** | 0.32 | 0.81 |
| Max Drawdown | **-27.2%** | -64.3% | -66.6% |
| Calmar Ratio | **1.79** | 0.25 | 0.61 |
| Final Equity | **5.63x** | 1.93x | 4.41x |
| Time-in-Market | 17% | 100% | 100% |
| Win Rate (traded) | **71.1%** | 50.4% | 57.1% |
| Avg Turnover | 9.6% | ,  | ,  |

The strategy beats both benchmarks on every metric, with higher final equity than EW Alts (5.63x vs 4.41x) and dramatically lower drawdown (-27.2% vs -66.6%). Calmar (1.79 vs 0.61) is the cleaner comparison. The regime gate buys risk-adjusted return, not raw return.

**2022 bear market:** Strategy is flat the entire year (BEAR regime). BTC draws down -64%; the strategy draws down 0%.

---

## 6. Factor Attribution -- What Actually Drives Performance

We removed each factor individually and measured the Sharpe impact (original 4-factor model, pre-May-7 baseline):

| Factor Removed | Sharpe | Delta |
|----------------|--------|-------|
| None (baseline) | 1.08 | -- |
| Price Momentum | 0.38 | **-0.70** |
| Funding Rate | 0.86 | **-0.22** |
| Revenue Growth | 1.09 | +0.01 |
| Activity Momentum | 1.09 | +0.01 |

**Finding:** Price momentum and funding rate account for 0.92 of the 1.08 Sharpe. Revenue growth and activity momentum contribute near zero value.

**Action taken (May 7):** Revenue growth and activity momentum were removed. The simplified 2-factor model (funding 45%, momentum 55%) achieves **Sharpe 1.31** on the current baseline.

**Current 2-factor attribution (shipped baseline):**

| Factor Removed | Sharpe | Max DD | Equity | Delta |
|----------------|--------|--------|--------|-------|
| None (baseline) | 1.31 | -27.2% | 5.63x | ,  |
| Price Momentum | 0.96 | -23.3% | 4.11x | **-0.35** |
| Funding Rate | 1.18 | -35.4% | 4.50x | **-0.13** |

Price momentum is now the dominant factor at the 7-week window. Removing it collapses Sharpe by 0.35. Removing funding rate drops Sharpe by 0.13. Both factors materially contribute; their relative importance shifts with the momentum window; at shorter lookbacks funding dominates, at longer windows momentum leads.

The on-chain factors are conceptually sound but data-limited; as Artemis expands coverage to more chains, their value should increase.

---

## 7. Known Limitations (Critical Evaluation)

1. **On-chain data coverage is narrow.** Only SOL and HYPE have Artemis fees/DAU data. The revenue growth and activity momentum factors were removed May 7 after factor attribution confirmed they contributed negligibly. This simplification is a feature: the model is now transparent about what drives its results.

2. **No historical OI data from Hyperliquid.** The OI confirmation factor (10%) was planned but impossible to implement. HL only exposes current OI snapshots, not time series.

3. **Equity perps are a stretch.** COIN, CRCL, and HOOD trade on HL perps but have no on-chain fundamentals. They compete purely on price momentum. Effectively they're treated as altcoins.

4. **Funding rate coverage is continuous post-May-2023.** SOL, BNB, and XMR carry non-zero funding in every single week from May 2023 onward. HYPE is the only asset with zero-funding weeks (pre-TGE, before Dec 2024). No week has all assets at zero. The model handles per-asset availability via cross-sectional normalization — an asset with zero funding competes against its peers that week, not against an absolute threshold.

5. **Backtest window is bounded by Hyperliquid's history, not by choice.** Jan 2022 is the earliest practical start: HL launched its perp dex in mid-2022 and `fundingHistory` returns from mid-2023 onward, so any earlier window would either drop the funding factor entirely or substitute non-HL funding data (which violates our price-source rule). The end of the window is simply the latest available week. The BTC regime gate (Layer 1) can be tested back to 2018 because it only needs price + on-chain data; that's a separate result reported in the BTC regime section.

6. **Short overlay tested and rejected (May 7, re-tested May 10).** A bear-market short leg during BEAR was tested with the same factor ranking. Original test (May 7): Sharpe collapsed from 1.13 to 0.48, max DD -75%. Re-test (May 10) against the then-current 1.31 baseline tested two variants: shorting bottom-2 (worst factor scores: Sharpe 0.10, DD -86.1%, equity 1.38x) and shorting top-2 (best factor scores: Sharpe 0.05, DD -81.7%, equity 1.18x). Both destroyed capital. The factor model identifies alts for longs, not directional shorts: bottom-ranked alts (poor momentum, positive funding) bounce during bear rallies, while top-ranked alts hold up better in downtrends. The qualitative result holds across all three baselines tested.

7. **Survivorship bias in universe selection.** All 7 assets existed for the full backtest window (or were added when they listed). There's no delisting or death filter.

8. **Transaction costs reduce net Sharpe.** The cost model charges HL taker fees (0.035%) plus tiered slippage (0.02-0.10%) on position changes only (entry, exit, rebalance turnover). Net Sharpe is 1.27 (3.1% drag), net equity 5.33x (5.3% drag), net annual return 47.0% (1.8pp drag). The strategy remains strongly positive after costs.

9. **Date-alignment bug caught and corrected (May 8).** A `-1 day` shift applied to all four equity-perp CSVs (assuming Saturday → Friday) was wrong for TAO (Friday) and CRCL (Monday), pushing those assets onto Thursday/Sunday rows that were filtered out at backtest time. As a side-effect, TAO's Thursday rows densified the price index and made `pct_change(periods=4)` look back 14 days instead of the documented 28. The blanket shift was replaced with a per-asset day-of-week alignment so every equity lands on Friday. A momentum-window sensitivity sweep confirmed the corrected 4-week lookback was a strong candidate; a subsequent 112-configuration optimization with Bybit XMR funding (May 9) selected 7 weeks as the final shipped value. TAO itself was removed entirely: it had been included as a shadow asset (allocation=0) to test whether the model would pick a narrative-driven AI coin without on-chain fundamentals, but the alignment bug meant it scored a flat 50 every week; the original shadow test never actually ran, and the documented "model rejects narrative coins" finding wasn't real evidence. We chose removal over fix-and-keep so the report doesn't carry an invalid validation; a proper version of that test would need a richer narrative-asset set, not TAO alone.

10. **HIP-3 equity splice (May 8).** Equity perp prices now come from Hyperliquid's HIP-3 `xyz` dex for any post-listing week, with yfinance only providing pre-listing backfill. This brings the codebase into compliance with CLAUDE.md decision #7 (HL primary for any HL-listed asset/period). Headline metrics did not move: BTC regime was BEAR throughout the entire post-listing window for COIN/HOOD/CRCL (Nov 2025 - present), so the strategy was flat and never used the post-listing data for any trades. The change is a correctness fix, not a metric improvement.

11. **BTC as tradeable position tested and rejected (May 10).** BTC was added to the investable universe (8 assets), with HL price and funding data pulled from Hyperliquid's main dex (BTC funding on HL begins May 2023; pre-May-2023 weeks get neutral 50 on the funding factor). The result: Sharpe dropped from 1.31 to 1.13, final equity from 5.63x to 4.41x. BTC was never selected in any of the 38 BULL weeks; during risk-on regimes, high-beta alts (SOL, HOOD, COIN) outrun BTC on both price momentum and funding rate. The 8th asset still hurts because it changes the cross-sectional normalization denominator (n−1 from 6 to 7), shifting scores for all assets. This validates the two-layer architecture: BTC's edge is as a regime gate signal, not a position. The regime gate already holds BTC's informational value; holding BTC directly is redundant in BULL and wrong in BEAR/NEUTRAL (where the strategy is flat). Documented as honest negative finding.

---

## 8. Data Sources

| Source | What | Frequency |
|--------|------|-----------|
| Hyperliquid API (main) | Token perp prices and funding rates for SOL/BNB/HYPE/XMR, OI snapshot | Weekly (Friday close) |
| Hyperliquid API (HIP-3 `xyz` dex) | Equity perp prices for COIN, HOOD, CRCL, used from each asset's HL listing date forward | Weekly (Friday close) |
| Artemis API | BTC price, protocol fees, DAU for SOL/HYPE | Weekly |
| Artemis API | BTC weekly close | Weekly (Friday close) |
| yfinance (via Python) | Pre-HL-listing price backfill only (COIN, HOOD, CRCL before HL listed them) | Weekly |
| Bybit API | Linear-perp funding for SOL, BNB (pre-May-2023) and XMR (pre-2026-01-16). XMR splice is signal-critical (XMR is picked in 24% of BULL weeks, all in the Bybit window); SOL/BNB splice is precautionary (the Jan 2022 → Apr 2023 pre-HL window is entirely BEAR/NEUTRAL, so it affects zero picks but is retained for methodological consistency: "HL where available, Bybit as cross-venue proxy where not"). | Weekly |
| CoinMetrics | MVRV Z-Score (via ImNuza) | Weekly |
| FRED | Fed Balance Sheet (via ImNuza) | Weekly |
| ImNuza's pipeline | BTC regime CSV (optionB) | Weekly |

Price source rule: Hyperliquid is the primary source for every asset in the universe; we trade on HL, so HL's mark/close is the correct fill reference. BTC weekly close comes from Artemis. yfinance is only used to backfill equity prices before HL listing (so the backtest can extend to Jan 2022 even for assets HL listed later).

---

## 9. Reproducibility

Code is split between `strategy/alts/` (Xynerss) and `strategy/btc_regime/` (ImNuza), with shared data fetchers in `strategy/data_pull/`:

| Script | Purpose |
|--------|---------|
| `strategy/alts/backtest.py` | Main backtest engine; run this to reproduce all results |
| `strategy/alts/sensitivity.py` | BULL threshold sensitivity analysis |
| `strategy/alts/factor_attribution.py` | Factor attribution (remove each factor) |
| `strategy/alts/momentum_sensitivity.py` | Momentum-window sensitivity sweep ({2,3,4,5,6,7,8,10} weeks) |
| `strategy/alts/walkforward.py` | Train/test split validation |
| `strategy/alts/cost_model.py` | Transaction cost model |
| `strategy/alts/monte_carlo.py` | Monte Carlo stress testing (250 randomized runs) |
| `strategy/alts/position_log.py` | Regenerate `docs/position_log.md` (full week-by-week trace) |
| `strategy/data_pull/hl_data_pull.py` | Token perps (SOL/BNB/HYPE/XMR) from HL main dex |
| `strategy/data_pull/pull_hl_equities.py` | Equity perps (COIN/HOOD/CRCL) from HL HIP-3 `xyz` dex |
| `strategy/data_pull/pull_equities.py` | yfinance pre-HL-listing backfill for equity perps |
| `strategy/data_pull/artemis_data_pull.py` | Refresh Artemis fees + DAU data |
| `strategy/btc_regime/run.py` | Regenerate the BTC regime CSV |

Dependencies: `pandas`, `numpy`, `requests`, `yfinance`, `scipy`, `matplotlib`

The regime CSV (`data/alts/btc_regime_weekly_optionB.csv`) is ImNuza's output. To update it, run `python -m strategy.btc_regime.run`. The backtest picks it up automatically.

---

## 10. Submission Checklist

Status as of 2026-05-16.

**Done**
- [x] All data files included in repo (`data/alts/`, `data/btc/`)
- [x] `requirements.txt` for Python dependencies
- [x] Reproduction instructions (`README.md` Quick Start + this file §9)
- [x] ImNuza's regime pipeline code included (`strategy/btc_regime/`)
- [x] Internal explainer drafted (this file)
- [x] Full week-by-week position log (`docs/position_log.md`)
- [x] Code fixes applied (chart title 6→5 factor, regime output path, equity_rev passthrough, dead code cleanup)
- [x] Full analysis suite verified (all 8 scripts run clean)
- [x] Data integrity audit passed (splices within 1%, no price gaps during BULL weeks, all sources aligned)
- [x] Turnover tracking + traded-week win rate added to backtest engine
- [x] Report polished (turnover/win rate in headline table, abstract trimmed, 10 structural fixes applied, section numbering reflowed)
- [x] Competition PDF requirements cross-referenced; all strategy requirements met
- [x] Git initialised, committed, and pushed to public GitHub (`github.com/ImNuza/artemis-juara`)

**Optional polish**
- [ ] Refresh data via the pull scripts; rerun analysis suite. Update headline numbers if they shift materially.
- [ ] Walk a fresh-clone reproduction of `README.md` Quick Start to verify Sharpe 1.31 / DD -27.2% / 5.63x reproduces.

**Send to:** `lindsey@artemisanalytics.xyz` by June 1, 2026 @ 11:59pm EST
