# Position Log -  BTC Regime-Gated Alt Factor Strategy

Auto-generated from the integrated backtest (`strategy/alts/backtest.py`). Re-run `python strategy/alts/position_log.py` to refresh.

**Note:** BTC is the regime gate signal only ,  it is never held as a position. The strategy trades alt perps on Hyperliquid; BTC price and on-chain data determine whether the strategy is deployed (BULL) or flat (BEAR/NEUTRAL).

_Window: 2022-01-07 → 2026-05-08._

---


## 1. Headline Metrics

- **Window:** 2022-01-07 → 2026-05-08 (227 weekly bars)
- **Sharpe:** 1.31
- **Max Drawdown:** -27.2%
- **Final Equity:** 5.63x
- **Annualised Return:** 48.8%
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
| SOL | 24 | 63% | 32% |
| BNB | 24 | 63% | 35% |
| HYPE | 8 | 21% | 30% |
| XMR | 9 | 24% | 34% |
| COIN | 24 | 63% | 33% |
| CRCL | 1 | 3% | 38% |
| HOOD | 24 | 63% | 34% |

## 4. Year-by-Year Breakdown

| Year | Weeks | BULL weeks | Weeks traded | Year return | Max leverage | End equity |
|---|---|---|---|---|---|---|
| 2022 | 52 | 0 | 0 | +0.0% | 0.0x | 1.00x |
| 2023 | 52 | 2 | 2 | +41.7% | 2.5x | 1.42x |
| 2024 | 52 | 24 | 24 | +205.0% | 2.5x | 3.54x |
| 2025 | 52 | 12 | 12 | +42.7% | 2.5x | 5.63x |
| 2026 | 19 | 0 | 0 | +0.0% | 0.0x | 5.63x |

## 5. Full Position Log (Every BULL Week)

These are all the weeks the strategy actually had capital deployed. Each row is a single weekly rebalance: the regime/score is the **previous** week's value (T-1 lag), the leverage is selected by that BTC score, and the positions are signal-weighted top-3 alts capped at 40% per asset.

| Week | BTC Score | Leverage | Positions | Weekly Return | Equity After |
|---|---:|---:|---|---:|---:|
| 2023-12-22 | 71 | 2.5x | COIN:36%, BNB:33%, SOL:31% | +34.48% | 1.345x |
| 2023-12-29 | 67 | 1.5x | COIN:36%, BNB:33%, SOL:31% | +5.40% | 1.417x |
| 2024-01-05 | 71 | 2.5x | COIN:36%, BNB:33%, SOL:31% | -18.19% | 1.160x |
| 2024-01-12 | 64 | 1.5x | COIN:36%, BNB:33%, SOL:31% | -9.78% | 1.046x |
| 2024-01-19 | 68 | 1.5x | BNB:38%, HOOD:33%, SOL:29% | +4.04% | 1.088x |
| 2024-01-26 | 69 | 1.5x | BNB:35%, SOL:34%, HOOD:31% | -2.33% | 1.063x |
| 2024-02-02 | 62 | 1.5x | BNB:40%, XMR:31%, SOL:29% | +6.74% | 1.135x |
| 2024-02-16 | 64 | 1.5x | XMR:34%, BNB:33%, SOL:33% | +9.06% | 1.238x |
| 2024-02-23 | 61 | 1.5x | BNB:40%, HOOD:35%, XMR:25% | +11.16% | 1.376x |
| 2024-03-01 | 73 | 2.5x | HOOD:39%, BNB:36%, COIN:25% | +26.20% | 1.736x |
| 2024-03-08 | 70 | 2.5x | COIN:36%, BNB:34%, HOOD:30% | +15.99% | 2.014x |
| 2024-03-15 | 75 | 2.5x | COIN:40%, HOOD:35%, BNB:25% | +24.40% | 2.505x |
| 2024-03-22 | 86 | 2.5x | COIN:40%, HOOD:35%, BNB:25% | +4.50% | 2.618x |
| 2024-03-29 | 95 | 2.5x | BNB:40%, COIN:32%, SOL:28% | +9.29% | 2.861x |
| 2024-04-05 | 81 | 2.5x | COIN:39%, BNB:36%, HOOD:25% | -4.84% | 2.723x |
| 2024-04-12 | 78 | 2.5x | BNB:40%, SOL:32%, COIN:28% | -17.60% | 2.244x |
| 2024-04-19 | 78 | 2.5x | BNB:40%, SOL:32%, COIN:28% | -4.80% | 2.136x |
| 2024-04-26 | 80 | 2.5x | BNB:40%, COIN:32%, SOL:28% | +2.09% | 2.180x |
| 2024-05-03 | 69 | 1.5x | BNB:40%, HOOD:32%, SOL:28% | -4.48% | 2.083x |
| 2024-05-10 | 65 | 1.5x | BNB:40%, HOOD:37%, COIN:23% | +14.59% | 2.387x |
| 2024-06-07 | 60 | 1.5x | XMR:40%, HOOD:40%, SOL:20% | +2.27% | 2.441x |
| 2024-11-29 | 67 | 1.5x | COIN:40%, HOOD:40%, XMR:20% | +15.44% | 2.818x |
| 2024-12-06 | 71 | 2.5x | COIN:38%, SOL:33%, HOOD:30% | -14.40% | 2.412x |
| 2024-12-13 | 73 | 2.5x | SOL:40%, COIN:33%, HYPE:27% | +11.79% | 2.696x |
| 2024-12-20 | 72 | 2.5x | HYPE:35%, SOL:34%, COIN:31% | +28.64% | 3.468x |
| 2024-12-27 | 71 | 2.5x | HOOD:36%, SOL:34%, COIN:30% | +1.99% | 3.537x |
| 2025-01-03 | 77 | 2.5x | XMR:40%, HOOD:38%, SOL:22% | +11.58% | 3.947x |
| 2025-01-10 | 61 | 1.5x | XMR:39%, HOOD:35%, BNB:26% | +8.74% | 4.292x |
| 2025-05-30 | 60 | 1.5x | XMR:35%, HOOD:35%, COIN:29% | -1.35% | 4.234x |
| 2025-06-06 | 61 | 1.5x | XMR:40%, HOOD:30%, HYPE:30% | -1.70% | 4.162x |
| 2025-06-13 | 64 | 1.5x | HOOD:37%, SOL:32%, HYPE:31% | +17.02% | 4.870x |
| 2025-06-27 | 61 | 1.5x | HOOD:37%, BNB:31%, COIN:31% | +8.26% | 5.272x |
| 2025-08-01 | 64 | 1.5x | CRCL:38%, COIN:33%, HOOD:29% | +2.66% | 5.413x |
| 2025-08-08 | 67 | 1.5x | HOOD:36%, HYPE:36%, COIN:28% | +5.27% | 5.698x |
| 2025-08-15 | 66 | 1.5x | SOL:39%, HOOD:37%, COIN:24% | +0.81% | 5.744x |
| 2025-08-22 | 65 | 1.5x | SOL:40%, HOOD:34%, HYPE:26% | +0.10% | 5.750x |
| 2025-08-29 | 66 | 1.5x | BNB:36%, HYPE:33%, SOL:31% | -2.64% | 5.598x |
| 2025-09-05 | 63 | 1.5x | BNB:40%, SOL:35%, HYPE:25% | +0.62% | 5.633x |

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
