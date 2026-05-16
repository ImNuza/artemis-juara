# Artemis Quant Competition 2026 — Track 1

**Team:** ImNuza (BTC regime gate) + Xynerss (alt factor engine)
**Deadline:** June 1, 2026 @ 11:59pm EST
**Submission:** lindsey@artemisanalytics.xyz

## Quick Start

```bash
pip install -r requirements.txt

# Run integrated backtest
python strategy/alts/backtest.py

# Analysis scripts
python strategy/alts/walkforward.py
python strategy/alts/cost_model.py
python strategy/alts/monte_carlo.py
python strategy/alts/sensitivity.py
python strategy/alts/factor_attribution.py
python strategy/alts/momentum_sensitivity.py
python strategy/alts/position_log.py
```

## Strategy

Two-layer system on Hyperliquid Perps, weekly rebalance:

1. **BTC Regime Gate (ImNuza):** 5-factor composite score classifies market as BULL/BEAR/NEUTRAL
2. **Alt Factor Engine (Xynerss):** 2-factor ranking (funding rate 45%, price momentum 55% over a 7-week window), top-3 with 40% cap

**Results:** Sharpe 1.31, max DD -27.2%, final equity 5.63x (net of costs: Sharpe 1.27, 5.33x). Phantom-pick gate excludes assets before they existed (HYPE pre-TGE, CRCL pre-IPO). XMR funding is Bybit-spliced pre-HL-listing (2026-01-16) for real signal across the full backtest.

Full optimization sweep at `results/integrated/optimization_sweep.csv`.

For a week-by-week trace of every position the strategy held, see [`docs/position_log.md`](docs/position_log.md).

## Structure

```
strategy/
├── btc_regime/    # ImNuza: BTC regime gate
├── alts/          # Xynerss: integrated backtest + analysis
└── data_pull/     # Data fetch scripts (HL main, HL HIP-3 equities, Artemis)
data/
├── btc/           # BTC regime inputs
└── alts/          # Alt prices, funding, fees, regime CSV
results/
├── btc_regime/    # Regime charts + CSVs
└── integrated/    # Backtest chart, walkforward, cost, Monte Carlo
docs/              # All documentation
```

## Reproducibility

All data files are in `data/`. The regime CSV (`data/alts/btc_regime_weekly_optionB.csv`) is ImNuza's output. Run `python -m strategy.btc_regime.run` to regenerate it (requires Artemis API key in `config.env`). The backtest picks it up automatically.
