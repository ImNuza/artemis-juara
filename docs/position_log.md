# Position Log — BTC Regime-Gated Alt Factor Strategy

Auto-generated from the integrated backtest (`strategy/alts/backtest.py`). Re-run `python strategy/alts/position_log.py` to refresh.

_Window: 2022-01-07 → 2026-05-08._

---


## 1. Headline Metrics

- **Window:** 2022-01-07 → 2026-05-08 (227 weekly bars)
- **Sharpe:** 1.15
- **Max Drawdown:** -16.4%
- **Final Equity:** 4.95x
- **Annualised Return:** 44.5%
- **Time in Market:** 38/227 weeks (17%)

## 2. Regime Distribution

| Regime | Weeks | Share |
|---|---:|---:|
| BULL | 38 | 17% |
| NEUTRAL | 73 | 32% |
| BEAR | 115 | 51% |
| INIT | 1 | 0% |

Strategy deploys capital only in BULL. NEUTRAL and BEAR are flat.

## 3. Asset Selection Frequency

Across **38 weeks** where the strategy was deployed:

| Asset | Weeks Selected | % of BULL Weeks | Avg Weight When Held |
|---|---:|---:|---:|
| SOL | 17 | 45% | 32% |
| BNB | 24 | 63% | 36% |
| HYPE | 24 | 63% | 31% |
| XMR | 9 | 24% | 35% |
| COIN | 15 | 39% | 35% |
| CRCL | 5 | 13% | 28% |
| HOOD | 20 | 53% | 33% |

## 4. Year-by-Year Breakdown

| Year | Weeks | BULL weeks | Weeks traded | Year return | Max leverage | End equity |
|---|---|---|---|---|---|---|
| 2022 | 52 | 0 | 0 | +0.0% | 0.0x | 1.00x |
| 2023 | 52 | 2 | 2 | +14.0% | 2.5x | 1.14x |
| 2024 | 52 | 24 | 24 | +172.2% | 2.5x | 2.96x |
| 2025 | 52 | 12 | 12 | +56.3% | 2.5x | 4.95x |
| 2026 | 19 | 0 | 0 | +0.0% | 0.0x | 4.95x |

## 5. Full Position Log (Every BULL Week)

These are all the weeks the strategy actually had capital deployed. Each row is a single weekly rebalance: the regime/score is the **previous** week's value (T-1 lag), the leverage is selected by that BTC score, and the positions are signal-weighted top-3 alts capped at 40% per asset.

| Week | BTC Score | Leverage | Positions | Weekly Return | Equity After |
|---|---:|---:|---|---:|---:|
| 2023-12-22 | 71 | 2.5x | COIN:39%, HOOD:33%, SOL:27% | +21.68% | 1.217x |
| 2023-12-29 | 67 | 1.5x | HOOD:39%, COIN:33%, SOL:27% | -6.31% | 1.140x |
| 2024-01-05 | 71 | 2.5x | BNB:37%, HOOD:35%, HYPE:28% | -4.61% | 1.087x |
| 2024-01-12 | 64 | 1.5x | BNB:40%, HYPE:30%, COIN:30% | -5.41% | 1.029x |
| 2024-01-19 | 68 | 1.5x | BNB:40%, HYPE:30%, CRCL:30% | +3.47% | 1.064x |
| 2024-01-26 | 69 | 1.5x | BNB:34%, HYPE:33%, XMR:33% | -1.70% | 1.046x |
| 2024-02-02 | 62 | 1.5x | BNB:39%, SOL:33%, HYPE:27% | +4.30% | 1.091x |
| 2024-02-16 | 64 | 1.5x | XMR:39%, COIN:33%, HYPE:27% | -3.41% | 1.054x |
| 2024-02-23 | 61 | 1.5x | COIN:39%, HOOD:33%, SOL:27% | +17.57% | 1.239x |
| 2024-03-01 | 73 | 2.5x | HOOD:39%, COIN:33%, SOL:27% | +43.22% | 1.775x |
| 2024-03-08 | 70 | 2.5x | COIN:39%, HOOD:33%, BNB:27% | +13.14% | 2.008x |
| 2024-03-15 | 75 | 2.5x | COIN:39%, HOOD:33%, BNB:27% | +26.65% | 2.543x |
| 2024-03-22 | 86 | 2.5x | BNB:39%, SOL:33%, HYPE:27% | -16.40% | 2.126x |
| 2024-03-29 | 95 | 2.5x | BNB:39%, SOL:33%, HYPE:27% | +18.38% | 2.517x |
| 2024-04-05 | 81 | 2.5x | BNB:34%, HYPE:33%, COIN:33% | -3.44% | 2.430x |
| 2024-04-12 | 78 | 2.5x | BNB:39%, HYPE:31%, CRCL:31% | +2.91% | 2.501x |
| 2024-04-19 | 78 | 2.5x | BNB:34%, HYPE:33%, COIN:33% | +3.63% | 2.592x |
| 2024-04-26 | 80 | 2.5x | BNB:36%, HOOD:35%, HYPE:29% | +7.57% | 2.788x |
| 2024-05-03 | 69 | 1.5x | BNB:39%, COIN:33%, HYPE:27% | -6.09% | 2.618x |
| 2024-05-10 | 65 | 1.5x | BNB:39%, HOOD:33%, HYPE:27% | +11.74% | 2.926x |
| 2024-06-07 | 60 | 1.5x | SOL:39%, XMR:33%, HYPE:27% | +0.91% | 2.952x |
| 2024-11-29 | 67 | 1.5x | COIN:39%, SOL:33%, HYPE:27% | +6.81% | 3.153x |
| 2024-12-06 | 71 | 2.5x | COIN:39%, HOOD:33%, SOL:27% | -14.20% | 2.705x |
| 2024-12-13 | 73 | 2.5x | SOL:39%, HOOD:33%, HYPE:27% | +18.44% | 3.204x |
| 2024-12-20 | 72 | 2.5x | HOOD:39%, BNB:33%, XMR:27% | -7.39% | 2.967x |
| 2024-12-27 | 71 | 2.5x | XMR:39%, BNB:33%, CRCL:27% | -0.24% | 2.960x |
| 2025-01-03 | 77 | 2.5x | XMR:40%, BNB:31%, CRCL:29% | +7.05% | 3.169x |
| 2025-01-10 | 61 | 1.5x | BNB:40%, XMR:35%, CRCL:25% | -2.28% | 3.097x |
| 2025-05-30 | 60 | 1.5x | HYPE:38%, XMR:33%, HOOD:29% | -3.24% | 2.997x |
| 2025-06-06 | 61 | 1.5x | HYPE:38%, XMR:33%, HOOD:29% | -0.72% | 2.975x |
| 2025-06-13 | 64 | 1.5x | HYPE:38%, HOOD:33%, COIN:29% | +31.02% | 3.898x |
| 2025-06-27 | 61 | 1.5x | HYPE:38%, HOOD:33%, COIN:29% | +12.47% | 4.384x |
| 2025-08-01 | 64 | 1.5x | HYPE:38%, SOL:33%, HOOD:29% | -8.73% | 4.001x |
| 2025-08-08 | 67 | 1.5x | SOL:38%, BNB:33%, HYPE:29% | +11.18% | 4.449x |
| 2025-08-15 | 66 | 1.5x | HOOD:38%, BNB:33%, SOL:29% | +1.94% | 4.535x |
| 2025-08-22 | 65 | 1.5x | BNB:38%, SOL:33%, HOOD:29% | +7.07% | 4.856x |
| 2025-08-29 | 66 | 1.5x | BNB:38%, HYPE:33%, SOL:29% | -2.52% | 4.733x |
| 2025-09-05 | 63 | 1.5x | BNB:38%, SOL:33%, HOOD:29% | +4.63% | 4.952x |

## 6. Compact Regime Timeline

Consecutive weeks of the same regime, collapsed:

| Regime | Start | End | Weeks |
|---|---|---|---:|
| INIT | 2022-01-07 | 2022-01-07 | 1 |
| BEAR | 2022-01-14 | 2023-06-09 | 74 |
| NEUTRAL | 2023-06-16 | 2023-06-16 | 1 |
| BEAR | 2023-06-23 | 2023-07-07 | 3 |
| NEUTRAL | 2023-07-14 | 2023-07-28 | 3 |
| BEAR | 2023-08-04 | 2023-08-04 | 1 |
| NEUTRAL | 2023-08-11 | 2023-08-11 | 1 |
| BEAR | 2023-08-18 | 2023-08-25 | 2 |
| NEUTRAL | 2023-09-01 | 2023-09-01 | 1 |
| BEAR | 2023-09-08 | 2023-11-03 | 9 |
| NEUTRAL | 2023-11-10 | 2023-12-15 | 6 |
| BULL | 2023-12-22 | 2024-02-02 | 7 |
| NEUTRAL | 2024-02-09 | 2024-02-09 | 1 |
| BULL | 2024-02-16 | 2024-05-10 | 13 |
| NEUTRAL | 2024-05-17 | 2024-05-31 | 3 |
| BULL | 2024-06-07 | 2024-06-07 | 1 |
| NEUTRAL | 2024-06-14 | 2024-11-22 | 24 |
| BULL | 2024-11-29 | 2025-01-10 | 7 |
| NEUTRAL | 2025-01-17 | 2025-04-18 | 14 |
| BEAR | 2025-04-25 | 2025-04-25 | 1 |
| NEUTRAL | 2025-05-02 | 2025-05-23 | 4 |
| BULL | 2025-05-30 | 2025-06-13 | 3 |
| NEUTRAL | 2025-06-20 | 2025-06-20 | 1 |
| BULL | 2025-06-27 | 2025-06-27 | 1 |
| NEUTRAL | 2025-07-04 | 2025-07-25 | 4 |
| BULL | 2025-08-01 | 2025-09-05 | 6 |
| NEUTRAL | 2025-09-12 | 2025-11-14 | 10 |
| BEAR | 2025-11-21 | 2026-05-08 | 25 |
