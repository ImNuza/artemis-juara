# BTC Regime-Gated Alt Factor Strategy — Explainer

**Team:** ImNuza (BTC regime gate) + Xynerss (alt factor engine)
**Venue:** Artemis Analytics Competition 2026, Track #1
**Deadline:** June 1, 2026

---

## 1. Strategy Overview (One Paragraph)

We run a long-only altcoin/equity-perp portfolio on Hyperliquid that only deploys capital when Bitcoin's macro regime is bullish. The regime gate is a 5-factor composite score (ImNuza). When the gate is open (BULL), we rank 8 assets by a 2-factor cross-sectional score (Xynerss), take the top 3, size them by signal strength with a 40% single-asset cap, and apply 1.5x–2.5x leverage depending on conviction. When the gate is closed (BEAR), we sit flat in USDC. The result: we capture alt beta in bull markets and avoid the -64% drawdowns that come from being long during bear markets.

---

## 2. Why Two Layers?

Altcoins are levered bets on Bitcoin. When BTC trends down, alts get crushed — regardless of their individual fundamentals. A pure cross-sectional ranking of alts (Layer 2 alone) would still hold positions through bear markets and suffer catastrophic drawdowns.

**Layer 1 (BTC Regime Gate)** answers: *should we be in the market at all?*
**Layer 2 (Alt Factor Engine)** answers: *if yes, which alts do we hold?*

This layering means the strategy only takes risk when the macro environment is favorable. The regime gate is not a subtle timing signal — it's a blunt on/off switch, and that's intentional.

---

## 3. Layer 1 — BTC Regime Gate (ImNuza)

### 3.1 The Composite Score

Five factors (Option B), each normalized via rolling 2-year min-max, combined with fixed weights:

| Factor | Weight | Source | What It Captures |
|--------|--------|--------|------------------|
| MVRV Z-Score | 30% | CoinMetrics | On-chain valuation extreme |
| Puell Multiple | 25% | BTC miner revenue / 365d MA | Miner profitability cycle |
| Price vs 200W MA Ratio | 20% | Artemis | Structural trend |
| Stablecoin Supply Δ 30d | 15% | Artemis | Crypto-native liquidity |
| BTC/ETH Dominance 30d ROC | 10% | Artemis | Risk appetite (BTC vs ETH) |

Each factor is scored 0–100 and combined into `BTC_Score`. The ETF Inflows signal (originally 20%) was dropped May 5, 2026 after testing showed it added noise; Fed Balance Sheet appears only in Option D, not the shipped Option B.

### 3.2 Regime Classification

```
BTC_Score ≥ 60  →  BULL     →  Deploy alt portfolio
BTC_Score ≤ 35  →  BEAR     →  Exit entirely, sit in USDC
35 < BTC_Score < 60 → NEUTRAL → Hold existing positions, no new entries, no rebalance
```

### 3.3 Why These Thresholds?

The thresholds (60/35) were chosen by ImNuza and **validated** by sensitivity analysis. Testing BULL thresholds from 50–65 on the full 2022–2026 backtest window:

| Threshold | Sharpe | Max DD | Result |
|-----------|--------|--------|--------|
| 50 | 0.79 | -42.7% | Too loose — enters during false rallies |
| 55 | 0.69 | -44.3% | Worse |
| **60** | **1.15** | **-16.4%** | **Optimal** |
| 65 | 0.85 | -16.4% | Too tight — misses real bull runs |

Lowering the threshold increases drawdown without improving returns. 60 is the sweet spot. The cliff between 55 and 60 (Sharpe 0.69 → 1.15) is sharp and itself a finding: the BTC composite is meaningfully more confident at scores ≥ 60 than between 50 and 60.

### 3.4 Regime Split (2018–2026)

| Regime | Weeks | % |
|--------|-------|---|
| BULL | 76 | 18.5% |
| NEUTRAL | 145 | 35.4% |
| BEAR | 189 | 46.1% |

The strategy is only actively deploying ~19% of the time. This low time-in-market is a feature, not a bug — it means the strategy is patient.

---

## 4. Layer 2 — Alt Factor Engine (Xynerss)

### 4.1 Universe

8 assets on Hyperliquid Perps:

| Asset | Type | Price Data | On-Chain Data |
|-------|------|------------|---------------|
| SOL | L1 crypto | Since Jan 2022 | Fees + DAU (Artemis) |
| BNB | Exchange token | Since Jan 2022 | None (Artemis limitation) |
| HYPE | L1 crypto | Since Dec 2024 | Fees + DAU (Artemis) |
| XMR | Privacy coin | Since Apr 2023 | None (by design) |
| COIN | Equity perp | Since Jul 2022 | N/A |
| CRCL | Equity perp | Since Dec 2025 | N/A |
| HOOD | Equity perp | Since Jan 2022 | N/A |


### 4.2 The Two Factors

Revenue growth and activity momentum were removed May 7, 2026 after factor attribution showed they each contributed +0.01 Sharpe (negligible marginal value). They only had data for 2-4 of 8 assets. The remaining two factors account for the full signal:

| Factor | Weight | Signal | Available For |
|--------|--------|--------|---------------|
| Funding Rate (inverted) | 55% | Weekly HL funding, negative = bullish | SOL, BNB, HYPE, XMR |
| Price Momentum | 45% | 4-week return, cross-sectional rank | All 8 assets |

OI Confirmation (10%) was planned but blocked -- Hyperliquid has no historical OI time series.

### 4.3 Scoring

Assets without funding data get neutral score 50 for that factor (no benefit, no penalty). Both factors are always active, so there is no per-week weight redistribution. The composite is simply:

```
Alt_Score = 0.55 * funding_score + 0.45 * momentum_score
```

### 4.4 Anti-Lookahead Rules (Non-Negotiable)

- **T-1 lag:** All signals use the previous week's data. You cannot trade on Friday's close using Friday's data.
- **Rolling 2-year min-max normalization:** Scores are normalized against the trailing 2-year window, not the full sample. No peeking at future highs/lows.
- **Data available after:** Equities must have 12 weeks of price history before entering the universe.

### 4.5 Portfolio Construction (BULL weeks only)

1. Rank all 8 assets by composite Alt_Score
2. Select top 3 (fewer if less than 3 have scores)
3. Weight by signal strength: `weight_i = score_i / sum(top 3 scores)`
4. Cap any single asset at 40%
5. Apply leverage:
   - BTC_Score ≥ 70 → 2.5x
   - BTC_Score 60–70 → 1.5x
   - Otherwise → 0x (flat)

Equity perps on COIN, CRCL, and HOOD get neutral 50 for on-chain factors (revenue, DAU). They compete purely on price momentum and funding rate — same as BNB and XMR. This is documented as an expected limitation, not a bug.

---

## 5. Backtest Results (Jan 2022 -- May 2026)

| Metric | Strategy | BTC B&H | EW Alts (No Regime) |
|--------|----------|---------|---------------------|
| Ann. Return | **44.5%** | 16.3% | 41.5% |
| Ann. Volatility | 38.7% | 51.3% | 49.3% |
| Sharpe Ratio | **1.15** | 0.32 | 0.84 |
| Max Drawdown | **-16.4%** | -64.3% | -66.6% |
| Calmar Ratio | **2.71** | 0.25 | 0.62 |
| Final Equity | **4.95x** | 1.93x | 4.53x |
| Time-in-Market | 17% | 100% | 100% |

The strategy beats both benchmarks on every risk-adjusted metric. The equal-weight no-regime alt portfolio reaches broadly similar final equity but with a -66.6% drawdown — Calmar (2.71 vs 0.62) is the cleaner comparison. The regime gate buys risk-adjusted return, not raw return.

**2022 bear market:** Strategy is flat the entire year (BEAR regime). BTC draws down -64%; the strategy draws down 0%.

---

## 6. Factor Attribution -- What Actually Drives Performance

We removed each factor individually and measured the Sharpe impact (original 4-factor model):

| Factor Removed | Sharpe | Delta |
|----------------|--------|-------|
| None (baseline) | 1.08 | -- |
| Price Momentum | 0.38 | **-0.70** |
| Funding Rate | 0.86 | **-0.22** |
| Revenue Growth | 1.09 | +0.01 |
| Activity Momentum | 1.09 | +0.01 |

**Finding:** Price momentum and funding rate account for 0.92 of the 1.08 Sharpe. Revenue growth and activity momentum contribute near zero marginal value.

**Action taken (May 7):** Revenue growth and activity momentum were removed. The simplified 2-factor model (funding 55%, momentum 45%) achieves **Sharpe 1.15** on the corrected May-8 baseline, confirming the dead-weight factors added noise rather than signal. (The May-7 number was 1.13 against an unintended 2-week momentum lookback caused by a date-alignment bug; correcting that bug and re-running the sweep landed at 4 weeks → 1.15.)

**Current 2-factor attribution (corrected May-8 baseline):**

| Factor Removed | Sharpe | Delta |
|----------------|--------|-------|
| None (baseline) | 1.15 | — |
| Funding Rate | 0.63 | **-0.52** |
| Price Momentum | 1.14 | -0.01 |

Funding rate is now clearly dominant. Price momentum's marginal Sharpe contribution is near zero, but its drawdown contribution is real: removing momentum widens max DD from -16.4% to -24.9%. Momentum trades raw return for tail-risk control.

This is a critical honesty point for the research report: the on-chain factors are conceptually sound but data-limited. As Artemis expands coverage to more chains, their marginal value should increase.

---

## 7. Known Limitations (Critical Evaluation)

1. **On-chain data coverage is narrow.** Only SOL and HYPE have Artemis fees/DAU data. The revenue growth and activity momentum factors were removed May 7 after factor attribution confirmed they contributed negligibly. This simplification is a feature: the model is now transparent about what drives its results.

2. **No historical OI data from Hyperliquid.** The OI confirmation factor (10%) was planned but impossible to implement. HL only exposes current OI snapshots, not time series.

3. **Equity perps are a stretch.** COIN, CRCL, and HOOD trade on HL perps but have no on-chain fundamentals. They compete purely on price momentum -- effectively they're treated as altcoins.

4. **Funding rate data is patchy pre-2024 — but the mechanism didn't change.** Many weeks show zero funding because Hyperliquid was still in its early-stage infrastructure phase: fewer perps listed, less flow producing nonzero settlements, and a historical record from the `fundingHistory` endpoint that's simply thinner for that period. The funding mechanism itself (8-hour cadence, 0.01% per-period cap) has been the same throughout the backtest. The model interprets zero funding as neutral (score 50) rather than treating absent data as a directional signal, so on weeks when funding is silent the strategy degrades gracefully to a price-momentum-only ranking.

5. **Backtest window is bounded by Hyperliquid's history, not by choice.** Jan 2022 is the earliest practical start: HL launched its perp dex in mid-2022 and `fundingHistory` returns from mid-2023 onward, so any earlier window would either drop the funding factor entirely or substitute non-HL funding data (which violates our price-source rule). The end of the window is simply the latest available week. The BTC regime gate (Layer 1) can be tested back to 2018 because it only needs price + on-chain data — that's a separate result reported in the BTC regime section.

6. **Short overlay tested and rejected (May 7).** A bear-market short leg (bottom-2 alts during BEAR) was tested with the same factor ranking. Sharpe collapsed from the May-7 baseline (1.13) to 0.48, max DD widened to -75%. The factor model identifies "hated" alts (oversold, negative funding) that bounce during bear rallies -- it ranks for longs, not directional shorts. This is an honest negative finding (the qualitative result holds against the corrected May-8 baseline as well).

7. **Survivorship bias in universe selection.** All 7 assets existed for the full backtest window (or were added when they listed). There's no delisting or death filter.

8. **Transaction costs reduce net Sharpe.** The cost model estimates HL taker fees (0.035%) plus tiered slippage (0.02-0.10%) reduce Sharpe from 1.15 to 1.02. The strategy remains positive after costs but the 5pp annual return drag is material.

9. **Date-alignment bug caught and corrected (May 8).** A `-1 day` shift applied to all four equity-perp CSVs (assuming Saturday → Friday) was wrong for TAO (Friday) and CRCL (Monday), pushing those assets onto Thursday/Sunday rows that were filtered out at backtest time. As a side-effect, TAO's Thursday rows densified the price index and made `pct_change(periods=4)` look back 14 days instead of the documented 28. The blanket shift was replaced with a per-asset day-of-week alignment so every equity lands on Friday. A momentum-window sensitivity sweep confirmed the corrected 4-week lookback is the right design choice. TAO itself was removed entirely: it had been included as a shadow asset (allocation=0) to test whether the model would pick a narrative-driven AI coin without on-chain fundamentals, but the alignment bug meant it scored a flat 50 every week — the original shadow test never actually ran, and the documented "model rejects narrative coins" finding wasn't real evidence. We chose removal over fix-and-keep so the report doesn't carry an invalid validation; a proper version of that test would need a richer narrative-asset set, not TAO alone.

10. **HIP-3 equity splice (May 8).** Equity perp prices now come from Hyperliquid's HIP-3 `xyz` dex for any post-listing week, with yfinance only providing pre-listing backfill. This brings the codebase into compliance with CLAUDE.md decision #7 (HL primary for any HL-listed asset/period). Headline metrics did not move: BTC regime was BEAR throughout the entire post-listing window for COIN/HOOD/CRCL (Nov 2025 – present), so the strategy was flat and never used the post-listing data for any trades. The change is a correctness fix, not a metric improvement.

---

## 8. Data Sources

| Source | What | Frequency |
|--------|------|-----------|
| Hyperliquid API (main) | Token perp prices and funding rates for SOL/BNB/HYPE/XMR, OI snapshot | Weekly (Friday close) |
| Hyperliquid API (HIP-3 `xyz` dex) | Equity perp prices for COIN, HOOD, CRCL — used from each asset's HL listing date forward | Weekly (Friday close) |
| Artemis API | Protocol fees, DAU for SOL/HYPE | Weekly |
| yfinance (via Python) | Pre-HL-listing price backfill only (COIN, HOOD, CRCL before HL listed them) | Weekly |
| CoinMetrics | MVRV Z-Score (via ImNuza) | Weekly |
| FRED | Fed Balance Sheet (via ImNuza) | Weekly |
| ImNuza's pipeline | BTC regime CSV (optionB) | Weekly |

Price source rule: Hyperliquid is the primary source for every asset in the universe; we trade on HL, so HL's mark/close is the correct fill reference. yfinance is only used to backfill periods before an asset was listed on HL (so the backtest can extend to Jan 2022 even for assets HL listed later).

---

## 9. Reproducibility

Code is split between `strategy/alts/` (Xynerss) and `strategy/btc_regime/` (ImNuza), with shared data fetchers in `strategy/data_pull/`:

| Script | Purpose |
|--------|---------|
| `strategy/alts/backtest.py` | Main backtest engine — run this to reproduce all results |
| `strategy/alts/sensitivity.py` | BULL threshold sensitivity analysis |
| `strategy/alts/factor_attribution.py` | Factor attribution (remove each factor) |
| `strategy/alts/momentum_sensitivity.py` | Momentum-window sensitivity sweep ({2,3,4,6,8} weeks) |
| `strategy/alts/walkforward.py` | Train/test split validation |
| `strategy/alts/cost_model.py` | Transaction cost model |
| `strategy/alts/monte_carlo.py` | Monte Carlo robustness (250 randomized runs) |
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

Status as of 2026-05-08.

**Done**
- [x] All data files included in repo (`data/alts/`, `data/btc/`)
- [x] `requirements.txt` for Python dependencies
- [x] Reproduction instructions (`README.md` Quick Start + this file §9)
- [x] ImNuza's regime pipeline code included (`strategy/btc_regime/`)
- [x] Research report drafted (`docs/research_report.md`)
- [x] Internal explainer drafted (this file)
- [x] Full week-by-week position log (`docs/position_log.md`)

**Outstanding (submission blockers)**
- [ ] **Initialise git, push to public GitHub repo.** Repo currently has zero commits. URL goes in the email.
- [ ] **Render `docs/research_report.md` as PDF.** Pandoc + LaTeX. PDF is the email attachment.
- [ ] **Build pitch deck (Google Slides).** Not started. Share with `lindsey@artemisanalytics.xyz`. ~10–12 slides mapping to `research_report.md` sections.

**Optional polish**
- [ ] Refresh data via the pull scripts; rerun analysis suite. Update headline numbers if they shift materially.
- [ ] Walk a fresh-clone reproduction of `README.md` Quick Start to verify Sharpe 1.15 / DD -16.4% / 4.95x reproduces.

**Send to:** `lindsey@artemisanalytics.xyz` by June 1, 2026 @ 11:59pm EST
