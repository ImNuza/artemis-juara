# Artemis Quant Competition -- CLAUDE.md

**Team:** ImNuza (BTC regime gate) + Xynerss (alt factor engine)
**Deadline:** June 1, 2026 @ 11:59pm EST
**Track:** #1 ,  BTC Regime-Gated Alt Factor Strategy (Hyperliquid Perps, weekly rebalance)

## Quick Orientation

Two-layer strategy:
1. **BTC Regime Gate (ImNuza)** ,  5-factor composite (0-100), BULL/BEAR/NEUTRAL, threshold 60/35
2. **Alt Factor Engine (Xynerss)** ,  2-factor ranking (funding 45%, momentum 55%), top-3, signal-weighted, 40% cap, momentum lookback 7 weeks

**Backtest (Jan 2022-May 2026, current code state):** Sharpe **1.31**, max DD -27.2%, **5.63x**, 17% time-in-market. Net: Sharpe 1.27, 5.33x.
**Bybit XMR funding** spliced pre-HL-listing (2026-01-16) so XMR has real funding signal across the full backtest. No gate needed.

**Prior baselines for context:**
- Pre-2026-05-09: Sharpe 1.15 / DD -16.4% / 4.95x ,  stale funding + XMR universe leakage
- Mid-session (HL-listing gate for all tokens): Sharpe 1.23 / DD -21.7% / 4.59x
- Phantom-only gate, 3w/55-45, HL-only XMR: Sharpe 0.99 / DD -29.8% / 3.84x
- Current (Bybit XMR, 7w/45-55, ImNuza regime): Sharpe 1.31 / DD -27.2% / 5.63x

## Structure

```
strategy/btc_regime/   ,  ImNuza: BTC composite, indicators, backtest
strategy/alts/          ,  Xynerss: integrated backtest + analysis scripts
strategy/data_pull/     ,  Data fetch scripts
data/btc/               ,  BTC regime inputs
data/alts/              ,  Alt prices, funding, fees, regime CSV
results/btc_regime/     ,  BTC regime outputs
results/integrated/     ,  Integrated backtest outputs
docs/                   ,  All documentation
archive/                ,  v1, experiments, old data
```

## Key Architecture Decisions (do not change without documenting)

1. **T-1 lag** ,  all signals use previous week's data. Non-negotiable.
2. **Rolling 2-year min-max normalization** ,  not full-sample.
3. **Regime thresholds** ,  BULL >= 60, BEAR <= 35. Under the current 7w/45-55 config the Sharpe-max threshold is 55 (1.46) not 60 (1.31), but 55 carries a deeper drawdown (-35.1% vs -27.2%) and 60 was retained for drawdown control and walk-forward conservatism (training-window optimum was 50, OOS Sharpe 2.07 with deeper DD). The "60 is Sharpe-optimal" claim was true under the prior 3w/55-45 config and is preserved here only as a deliberate risk-adjusted choice, not a Sharpe maximum.
4. **Top 3 assets** ,  signal-weighted, 40% cap. 1.5x-2.5x leverage tiers.
5. **Dynamic weights** ,  revenue/activity factors removed May 7 (+0.01 Sharpe each). Only funding + momentum remain.
6. **Short overlay** ,  tested May 7 and rejected (Sharpe collapse, large DD blow-up against the May-7 baseline). Re-tested May 10 against the then-current 1.31 baseline: shorting bottom-2 during BEAR (Sharpe 0.10, DD -86.1%, equity 1.38x) or top-2 during BEAR (Sharpe 0.05, DD -81.7%, equity 1.18x) both destroyed capital. Documented as honest negative finding. The qualitative result (short overlay destroys capital) has held across every baseline tested since.
7. **Price source hierarchy** ,  Hyperliquid is the primary price source for any asset/period during which it was listed on HL. Artemis API provides BTC weekly close. yfinance is used ONLY for equity pre-listing backfill (COIN/HOOD/CRCL before HIP-3 listing). Token perps (SOL/BNB/HYPE/XMR) come from the main HL dex; equity perps (COIN/HOOD/CRCL) come from the HIP-3 `xyz` dex from their listing dates (Nov-Dec 2025) forward. We trade on HL, so HL prices are the venue-correct fill reference; mixing yfinance for periods where HL has data introduces avoidable venue divergence.
8. **Phantom-pick gate (REVISED 2026-05-09 mid-session)** ,  `backtest.py:HL_TOKEN_LISTING` now contains only assets that did not exist anywhere on Earth before their gate date: HYPE (TGE 2024-11-29, gate 2024-12-06) and CRCL (IPO 2025-06-05, gate 2025-06-06). Picks of these assets pre-existence trigger the neutral-50 fillback in `compute_alt_scores` and would show as indefensible "we held HYPE before TGE" rows in the position log. The gate NaN's the composite so `run_backtest`'s `dropna()` excludes them. The earlier HL-listing-based gate was abandoned because it conflated phantom (asset doesn't exist) with venue-mismatch (asset existed on other venues, just not HL). SOL/BNB/XMR pre-HL-listing are venue-mismatch picks, not phantoms ,  they had real prices on other CEXes throughout the backtest. Note: the `CRCL_START` filter was removed so CRCL prices flow through from June 2025 IPO; the gate alone handles pre-IPO weeks.
9. **BTC as tradeable position** ,  tested May 10 and rejected. Adding BTC to the investable universe (8 assets instead of 7) drops Sharpe from 1.31 to 1.13 and final equity from 5.63x to 4.41x. BTC was never selected in any of the 38 BULL weeks ,  alts outrun it on both momentum and funding during risk-on regimes. Adding it still hurts because it changes the cross-sectional normalization denominator (n-1 from 6 to 7), shifting scores for all assets. The BTC regime gate already captures BTC's informational value; holding BTC directly is redundant in BULL (you want the higher-beta alts) and wrong in BEAR/NEUTRAL (strategy is flat anyway). Documented as honest negative finding.
10. **Bybit XMR funding splice + 7w/45-55 optimization (2026-05-09 end-of-session)** ,  XMR had near-zero HL funding for 140/157 weeks because it only listed on HL Jan 2026. The original phantom-only gate zeroed XMR funding as neutral-50, which made XMR dead weight (0 picks). Replaced with Bybit linear-perp funding pre-HL-listing (2026-01-16), giving XMR real signal across the full backtest. Systematic optimization over 112 configurations (7 momentum windows × 4 thresholds × 4 weight combos) confirmed: 7-week momentum lookback, 45/55 funding/momentum weights, ImNuza's threshold-60 regime as-is. Momentum is now the dominant factor (removing it costs 0.35 Sharpe vs 0.13 for funding). Results: Sharpe 1.31 (+0.32), DD -27.2% (+2.6pp), equity 5.63x (+1.79x) vs the phantom-only/3w/55-45 baseline. XMR goes from 0 picks to 9 picks (24% of BULL weeks), and asset selection diversifies from HOOD-dominated (89%) to evenly balanced across SOL/BNB/COIN/HOOD (63% each).
11. **HIP-3 equity funding (2026-05-10)** ,  Equity perps (COIN, HOOD, CRCL) now carry real funding rate data from their HIP-3 `xyz` dex listing dates forward (Nov-Dec 2025). `compute_funding_score` counts non-NaN assets from the input data so pre-listing weeks (equities = NaN) don't inflate the cross-sectional normalization denominator. Equities pre-listing get neutral-50 on funding; post-listing they compete in the cross-sectional rank normally. The data is pulled by `pull_hl_equities.py` and saved to `data/alts/equity_funding_hl.csv`. No backtest impact: the BTC regime has been BEAR/NEUTRAL since Nov 2025, so zero BULL weeks overlap with the equity funding window. This is a correctness fix ,  equities previously got neutral-50 on funding as an implicit "no data" fallback even though the data exists on HL.

## Running

```bash
# Integrated backtest
python strategy/alts/backtest.py

# Analysis
python strategy/alts/walkforward.py
python strategy/alts/cost_model.py
python strategy/alts/monte_carlo.py

# BTC regime standalone
python -m strategy.btc_regime.run
```

## Submission Requirements

Email lindsey@artemisanalytics.xyz: PDF report + GitHub repo + Google Slides deck.
Judging: Research Quality 30% | Signal Validity 30% | Critical Evaluation 20% | Communication 20%

## Next Steps (what's left before submission)

State as of 2026-05-12. Three submission blockers, then optional polish.

### Submission blockers (must do)

1. **Initialize git and push to public GitHub repo.**
   - Files staged (`git add`); needs `git config user.email/name`, then `git commit` and `git push`.
   - Create a public GitHub repo and push.
   - Verify `.gitignore` excludes `.env`, `venv/`, `.claude/`, `__pycache__/` ,  already configured.
   - The public repo URL is one of the three things the email needs.

2. **Render `docs/research_report.md` as PDF.**
   - Pandoc + LaTeX is the cleanest path: `pandoc docs/research_report.md -o docs/research_report.pdf` (with a sensible template).
   - Sanity-check that the section numbering, tables, and `backtest_results.png` reference all render correctly.
   - Resulting PDF is the email attachment.

3. **Build the pitch deck (Google Slides).**
   - Not started. Cover: problem framing, two-layer architecture diagram, headline metrics with comparison vs benchmarks, factor attribution chart, walk-forward + Monte Carlo, tested-and-rejected paths, limitations.
   - Share with `lindsey@artemisanalytics.xyz` (link is the second of three things the email needs).
   - Aim for ~10-12 slides. Each slide should map to a section of `docs/research_report.md`.

### Pre-submission polish (optional but worthwhile)

- **Refresh data** with the pull scripts before final commit so the repo ships with up-to-the-deadline data:
  - `python strategy/data_pull/hl_data_pull.py` (token perps + funding)
  - `python strategy/data_pull/pull_hl_equities.py` (HIP-3 equity perps)
  - `python strategy/data_pull/artemis_data_pull.py` (Artemis fees + DAU)
  - `python -m strategy.btc_regime.run` (regime CSV)
  - Re-run `python strategy/alts/backtest.py` and the analysis suite. Update headline numbers in CLAUDE.md / README.md / research_report.md if they shift.
- **Add a one-line BTC clarification** at the top of `docs/position_log.md` (BTC is the gate signal, not a position) ,  saves anyone reading the log cold from asking the same question.
- **Verify reproducibility** by walking through the README's Quick Start on a clean clone (or at least a fresh shell): `pip install -r requirements.txt` then run `strategy/alts/backtest.py`. Confirm Sharpe 1.31 / DD -27.2% / 5.63x.

### On submission day

Email `lindsey@artemisanalytics.xyz` with:
- PDF of `docs/research_report.md` attached
- Public GitHub repo URL
- Google Slides deck URL (shared with the same address)

Subject something like: "Artemis Quant Competition 2026 ,  Track 1 Submission ,  ImNuza & Xynerss".

### What's done (don't redo)

For context ,  the May 7-8 sessions covered: 4-factor → 2-factor model trim, short-overlay rejection, walk-forward + cost + Monte Carlo + factor attribution scripts, TAO removal + date-alignment fix + HIP-3 equity splice, momentum-window sensitivity sweep, full doc rewrite, position log generator, archive cleanup, Drive diff list. The May 12 session (part 1) covered: code fixes (chart title 6→5 factor, regime output path now writes to data/alts, equity_rev passthrough in sensitivity/factor_attribution, dead TEST_END constant removed), full 8-script analysis suite verified, data integrity audit passed (equity splices within 1%, no price gaps during BULL weeks, all sources aligned), files staged to git. The May 12 session (part 2) covered: turnover tracking + traded-week win rate added to backtest.py, competition PDF requirements cross-reference, 10 report fixes applied (abstract trimmed, §2 1.93x conflation fixed, §3.5 flat% clarified, §3.6 dollar→multiplier conversion, §5.2 per-asset blurbs trimmed, §6.1 walk-forward reframed, §6.3 Monte Carlo "95th percentile" softened, §7 historical note reduced to 1 sentence, §8.3 removed and folded into §8.2, §9 "Primary factor" corrected, §8 section numbering reflowed), NEUTRAL description fixed in strategy explainer, README analysis scripts list completed. The strategy and the active docs are in shipping shape. What's left is the wrapping (git commit/push, PDF, deck), not the research.
