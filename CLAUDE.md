# Artemis Quant Competition -- CLAUDE.md

**Team:** ImNuza (BTC regime gate) + Xynerss (alt factor engine)
**Deadline:** June 1, 2026 @ 11:59pm EST
**Track:** #1 — BTC Regime-Gated Alt Factor Strategy (Hyperliquid Perps, weekly rebalance)

## Quick Orientation

Two-layer strategy:
1. **BTC Regime Gate (ImNuza)** — 5-factor composite (0-100), BULL/BEAR/NEUTRAL, threshold 60/35
2. **Alt Factor Engine (Xynerss)** — 2-factor ranking (funding 55%, momentum 45%), top-3, signal-weighted, 40% cap

**Backtest (Jan 2022–May 2026):** Sharpe 1.15, max DD -16.4%, 4.95x, 17% time-in-market. Momentum lookback = 4 weeks (sensitivity sweep at `results/integrated/momentum_sensitivity.csv` confirmed robust across windows 3–6 weeks).
**Net of costs:** Sharpe 1.02, 4.23x.

## Structure

```
strategy/btc_regime/   — ImNuza: BTC composite, indicators, backtest
strategy/alts/          — Xynerss: integrated backtest + analysis scripts
strategy/data_pull/     — Data fetch scripts
data/btc/               — BTC regime inputs
data/alts/              — Alt prices, funding, fees, regime CSV
results/btc_regime/     — BTC regime outputs
results/integrated/     — Integrated backtest outputs
docs/                   — All documentation
archive/                — v1, experiments, old data
```

## Key Architecture Decisions (do not change without documenting)

1. **T-1 lag** — all signals use previous week's data. Non-negotiable.
2. **Rolling 2-year min-max normalization** — not full-sample.
3. **Regime thresholds** — BULL >= 60, BEAR <= 35. Sensitivity confirmed 60 is Sharpe-optimal.
4. **Top 3 assets** — signal-weighted, 40% cap. 1.5x-2.5x leverage tiers.
5. **Dynamic weights** — revenue/activity factors removed May 7 (+0.01 Sharpe each). Only funding + momentum remain.
6. **Short overlay** — tested May 7 and rejected (Sharpe collapse, large DD blow-up against the May-7 baseline). Documented as honest negative finding. The qualitative result holds against the corrected May-8 baseline; quantitative rerun on the 4-week momentum baseline is pending.
7. **Price source hierarchy** — Hyperliquid is the primary price source for any asset/period during which it was listed on HL. yfinance/Artemis are used ONLY to backfill history before the asset was listed on HL. Token perps (SOL/BNB/HYPE/XMR) come from the main HL dex; equity perps (COIN/HOOD/CRCL) come from the HIP-3 `xyz` dex from their listing dates (Nov–Dec 2025) forward. We trade on HL, so HL prices are the venue-correct fill reference; mixing yfinance for periods where HL has data introduces avoidable venue divergence.

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

State as of end-of-session 2026-05-08. Three submission blockers, then optional polish.

### Submission blockers (must do)

1. **Initialize git and push to public GitHub repo.**
   - `git add -A && git commit` from project root with a clean first-commit message.
   - Create a public GitHub repo and push.
   - Verify `.gitignore` excludes `.env`, `venv/`, `.claude/`, `__pycache__/` — already configured.
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
- **Add a one-line BTC clarification** at the top of `docs/position_log.md` (BTC is the gate signal, not a position) — saves anyone reading the log cold from asking the same question.
- **Verify reproducibility** by walking through the README's Quick Start on a clean clone (or at least a fresh shell): `pip install -r requirements.txt` then run `strategy/alts/backtest.py`. Confirm Sharpe 1.15 / DD -16.4% / 4.95x.

### On submission day

Email `lindsey@artemisanalytics.xyz` with:
- PDF of `docs/research_report.md` attached
- Public GitHub repo URL
- Google Slides deck URL (shared with the same address)

Subject something like: "Artemis Quant Competition 2026 — Track 1 Submission — ImNuza & Xynerss".

### What's done (don't redo)

For context — the May 7-8 sessions covered: 4-factor → 2-factor model trim, short-overlay rejection, walk-forward + cost + Monte Carlo + factor attribution scripts, TAO removal + date-alignment fix + HIP-3 equity splice, momentum-window sensitivity sweep, full doc rewrite, position log generator, archive cleanup, Drive diff list. The strategy and the active docs are in shipping shape. What's left is the wrapping (git, PDF, deck), not the research.
