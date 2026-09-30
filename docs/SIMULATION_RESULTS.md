# Résultats de simulation multi-horizons

> `python -m packages.backtest.grid_runner` · 2026-09-30 12:03 UTC · source **fmp** · grille `multi-horizons-2026-09-30` [900737b716db] · depuis 2020-01-01 · 4 actifs : NVDA, PLTR, BTCUSD, ETHUSD

Classement par Sharpe MÉDIAN entre actifs. DSR déflaté par tous les essais du programme (seuil de crédibilité 0,95). PBO > 0,5 : le classement est du bruit. « bat B&H » = part des fenêtres glissantes où la règle bat le buy & hold. Chaque colonne est une médiane INDÉPENDANTE entre actifs (un PF < 1 peut côtoyer un Sharpe positif) ; peu de trades par actif : win 100 % = 1 à 3 trades.

## Demandé mais non testable aujourd'hui (UNCALIBRATED)

| Élément | Raison |
|---|---|
| score_ml_xgboost_lightgbm | UNCALIBRATED — méta-filtre SMCLXTP-A : 54 événements < 200 |
| fondamentaux_pe_pb_roe_cfy | UNCALIBRATED — aucune base fondamentale point-in-time |
| deep_value_compounders_roe | UNCALIBRATED — idem (fondamentaux au présent = look-ahead) |
| regimes_macro_hmm | UNCALIBRATED — aucun modèle HMM dans le dépôt |
| fvg_order_blocks_institutional | UNCALIBRATED — institutional_price_action sans réglages |
| hrp_risk_parity_multi_facteurs | portefeuille, pas actif isolé : make explorer (870 scénarios VPS) |
| bande_adaptative_k_sigma | portefeuille : make preset-replay --bande adaptative |

## Court terme — timeframe daily (192 essais · fréquences jour, semaine)

| Horizon | Configuration (stratégie · sortie · fréquence) | Sharpe | DSR méd. | MaxDD | Calmar | Win | PF | Turnover/an | Rend. 1 an(s) · bat B&H |
|---|---|---|---|---|---|---|---|---|---|
| court | `momentum_12_1 · signal · jour` | 1.09 | 0.22 | -52.4% | 0.92 | 61% | 23.27 | 3.6 | +44.7% · 32% |
| court | `momentum_12_1 · tendance_mm200 · jour` | 1.09 | 0.17 | -51.1% | 0.95 | 39% | 4.95 | 3.7 | +29.7% · 36% |
| court | `ma_crossover · tendance_mm200 · jour` | 1.08 | 0.28 | -56.2% | 1.02 | 42% | 11.32 | 2.1 | +31.8% · 37% |
| court | `tendance_mm200 · suiveur_3atr · semaine` | 1.05 | 0.08 | -54.0% | 0.89 | 45% | 1.49 | 15.1 | +16.0% · 37% |
| court | `tendance_mm200 · signal · jour` | 1.05 | 0.27 | -56.9% | 0.92 | 25% | 5.56 | 4.3 | +31.6% · 36% |
| court | **buy & hold** | 1.01 | — | -78.0% | — | — | — | — | +62.4% |

PBO par actif : NVDA 0.26, PLTR 0.25, BTCUSD 0.59, ETHUSD 0.67

## Moyen terme — timeframe daily (96 essais · fréquences mois, trimestre)

| Horizon | Configuration (stratégie · sortie · fréquence) | Sharpe | DSR méd. | MaxDD | Calmar | Win | PF | Turnover/an | Rend. 3 an(s) · bat B&H | Rend. 5 an(s) · bat B&H |
|---|---|---|---|---|---|---|---|---|---|---|
| moyen | `momentum_12_1 · signal · trimestre` | 0.98 | 0.52 | -55.4% | 0.74 | 62% | 0.66 | 0.3 | +35.0% · 19% | +42.6% · 42% |
| moyen | `smclxtp · signal · mois` | 0.96 | 0.49 | -65.3% | 0.65 | 73% | 9.66 | 2.8 | +56.6% · 63% | +50.2% · 43% |
| moyen | `ma_crossover · tendance_mm200 · mois` | 0.95 | 0.48 | -54.7% | 0.81 | 50% | 4.03 | 1.2 | +47.5% · 41% | +46.6% · 5% |
| moyen | `smclxtp · tendance_mm200 · mois` | 0.93 | 0.45 | -54.7% | 0.74 | 50% | 2.78 | 1.2 | +43.0% · 34% | +41.9% · 0% |
| moyen | `tendance_mm200 · signal · trimestre` | 0.91 | 0.44 | -54.6% | 0.60 | 70% | 2.04 | 1.2 | +26.3% · 43% | +33.9% · 0% |
| moyen | **buy & hold** | 1.01 | — | -78.0% | — | — | — | — | +53.6% | +47.3% |

PBO par actif : NVDA 0.56, PLTR 0.53, BTCUSD 0.60, ETHUSD 0.90

## Long terme — timeframe daily (32 essais · fréquences trimestre, annee)

| Horizon | Configuration (stratégie · sortie · fréquence) | Sharpe | DSR méd. | MaxDD | Calmar | Win | PF | Turnover/an | Rend. 5 an(s) · bat B&H | Rend. 10 an(s) · bat B&H |
|---|---|---|---|---|---|---|---|---|---|---|
| long | `momentum_12_1 · signal · trimestre` | 0.98 | 0.87 | -55.4% | 0.74 | 62% | 0.66 | 0.3 | +42.6% · 42% | — · — |
| long | `tendance_mm200 · signal · trimestre` | 0.91 | 0.88 | -54.6% | 0.60 | 70% | 2.04 | 1.2 | +33.9% · 0% | — · — |
| long | `tendance_mm200 · tendance_mm200 · trimestre` | 0.91 | 0.88 | -54.6% | 0.60 | 70% | 2.04 | 1.2 | +33.9% · 0% | — · — |
| long | `momentum_12_1 · tendance_mm200 · trimestre` | 0.72 | 0.77 | -56.3% | 0.40 | 70% | 1.82 | 1.2 | +27.3% · 0% | — · — |
| long | `tendance_mm200 · signal · annee` | 0.71 | 0.71 | -59.7% | 0.39 | 100% | — | 0.3 | +29.1% · 20% | — · — |
| long | **buy & hold** | 1.01 | — | -78.0% | — | — | — | — | +47.3% | — |

PBO par actif : NVDA 0.32, PLTR 0.78, BTCUSD 0.26, ETHUSD 0.77

## Court terme — timeframe weekly (96 essais · fréquences semaine)

| Horizon | Configuration (stratégie · sortie · fréquence) | Sharpe | DSR méd. | MaxDD | Calmar | Win | PF | Turnover/an | Rend. 1 an(s) · bat B&H |
|---|---|---|---|---|---|---|---|---|---|
| court | `momentum_12_1 · signal · semaine` | 1.06 | 0.16 | -49.2% | 0.95 | 67% | 104.47 | 1.4 | +50.6% · 35% |
| court | `ma_crossover · signal · semaine` | 1.01 | 0.08 | -42.4% | 0.90 | 100% | 1.25 | 0.5 | +10.8% · 25% |
| court | `momentum_12_1 · tp_3atr · semaine` | 0.96 | 0.13 | -49.2% | 0.86 | 82% | 2.84 | 4.9 | +45.0% · 37% |
| court | `momentum_12_1 · suiveur_3atr · semaine` | 0.93 | 0.11 | -50.7% | 0.87 | 58% | 3.75 | 3.7 | +37.5% · 42% |
| court | `ma_crossover · suiveur_3atr · semaine` | 0.90 | 0.07 | -45.3% | 0.78 | 71% | 4.06 | 2.7 | +10.3% · 36% |
| court | **buy & hold** | 0.99 | — | -76.0% | — | — | — | — | +63.9% |

1 configuration(s) sans aucun trade (indicateur jamais défini sur cette barre) : exclues du classement.

PBO par actif : NVDA 0.33, PLTR 0.28, BTCUSD 0.08, ETHUSD 0.29

## Moyen terme — timeframe weekly (96 essais · fréquences mois, trimestre)

| Horizon | Configuration (stratégie · sortie · fréquence) | Sharpe | DSR méd. | MaxDD | Calmar | Win | PF | Turnover/an | Rend. 3 an(s) · bat B&H | Rend. 5 an(s) · bat B&H |
|---|---|---|---|---|---|---|---|---|---|---|
| moyen | `momentum_12_1 · signal · trimestre` | 1.05 | 0.82 | -49.4% | 0.88 | 100% | 1.48 | 0.3 | +40.7% · 20% | +50.0% · 42% |
| moyen | `ma_crossover · signal · mois` | 1.01 | 0.80 | -42.4% | 0.91 | 100% | 1.32 | 0.5 | +55.6% · 51% | +48.8% · 51% |
| moyen | `ma_crossover · signal · trimestre` | 0.93 | 0.75 | -45.3% | 0.88 | 100% | 1.70 | 0.4 | +54.4% · 23% | +49.3% · 41% |
| moyen | `ma_crossover · tp_3atr · mois` | 0.92 | 0.72 | -40.9% | 0.76 | 87% | 4.48 | 4.1 | +43.7% · 45% | +40.1% · 26% |
| moyen | `momentum_12_1 · signal · mois` | 0.84 | 0.67 | -58.7% | 0.66 | 50% | 6.66 | 0.6 | +42.3% · 8% | +46.4% · 11% |
| moyen | **buy & hold** | 0.99 | — | -76.0% | — | — | — | — | +54.0% | +48.8% |

2 configuration(s) sans aucun trade (indicateur jamais défini sur cette barre) : exclues du classement.

PBO par actif : NVDA 0.53, PLTR 0.34, BTCUSD 0.15, ETHUSD 0.50

## Long terme — timeframe weekly (32 essais · fréquences trimestre, annee)

| Horizon | Configuration (stratégie · sortie · fréquence) | Sharpe | DSR méd. | MaxDD | Calmar | Win | PF | Turnover/an | Rend. 5 an(s) · bat B&H | Rend. 10 an(s) · bat B&H |
|---|---|---|---|---|---|---|---|---|---|---|
| long | `momentum_12_1 · signal · trimestre` | 1.05 | 0.77 | -49.4% | 0.88 | 100% | 1.48 | 0.3 | +50.0% · 42% | — · — |
| long | `momentum_12_1 · signal · annee` | 0.66 | 0.49 | -70.5% | 0.29 | 100% | 1.88 | 0.3 | +20.5% · 0% | — · — |
| long | `tendance_mm200 · signal · trimestre` | 0.56 | 0.37 | -47.8% | 0.40 | 25% | 2.78 | 0.2 | +25.4% · 0% | — · — |
| long | `tendance_mm200 · tendance_mm200 · trimestre` | 0.56 | 0.37 | -47.8% | 0.40 | 25% | 2.78 | 0.2 | +25.4% · 0% | — · — |
| long | `momentum_12_1 · tendance_mm200 · trimestre` | 0.53 | 0.36 | -47.8% | 0.38 | 25% | 1.20 | 0.2 | +23.3% · 0% | — · — |
| long | **buy & hold** | 0.99 | — | -76.0% | — | — | — | — | +48.8% | — |

3 configuration(s) sans aucun trade (indicateur jamais défini sur cette barre) : exclues du classement.

PBO par actif : NVDA 0.42, PLTR 0.26, BTCUSD 0.02, ETHUSD 0.71

## Moyen terme — timeframe monthly (96 essais · fréquences mois, trimestre)

| Horizon | Configuration (stratégie · sortie · fréquence) | Sharpe | DSR méd. | MaxDD | Calmar | Win | PF | Turnover/an | Rend. 3 an(s) · bat B&H | Rend. 5 an(s) · bat B&H |
|---|---|---|---|---|---|---|---|---|---|---|
| moyen | `momentum_12_1 · signal · trimestre` | 0.95 | 0.31 | -49.0% | 0.87 | 62% | 0.66 | 0.3 | +35.1% · 19% | +42.8% · 42% |
| moyen | `momentum_12_1 · signal · mois` | 0.83 | 0.31 | -58.5% | 0.66 | 71% | 5.05 | 0.6 | +38.4% · 7% | +41.1% · 15% |
| moyen | `momentum_12_1 · tp_3atr · mois` | 0.82 | 0.28 | -58.5% | 0.57 | 71% | 2.30 | 2.4 | +32.0% · 3% | +33.9% · 8% |
| moyen | `momentum_12_1 · tp_3atr · trimestre` | 0.75 | 0.20 | -49.0% | 0.52 | 75% | 4.79 | 2.1 | +21.8% · 17% | +23.7% · 4% |
| moyen | **buy & hold** | 0.86 | — | -75.0% | — | — | — | — | +54.3% | +43.5% |

20 configuration(s) sans aucun trade (indicateur jamais défini sur cette barre) : exclues du classement.

PBO par actif : NVDA 0.00, PLTR 0.09, BTCUSD 0.03, ETHUSD 0.41

## Long terme — timeframe monthly (32 essais · fréquences trimestre, annee)

| Horizon | Configuration (stratégie · sortie · fréquence) | Sharpe | DSR méd. | MaxDD | Calmar | Win | PF | Turnover/an | Rend. 5 an(s) · bat B&H | Rend. 10 an(s) · bat B&H |
|---|---|---|---|---|---|---|---|---|---|---|
| long | `momentum_12_1 · signal · trimestre` | 0.95 | 0.19 | -49.0% | 0.87 | 62% | 0.66 | 0.3 | +42.8% · 42% | — · — |
| long | `momentum_12_1 · signal · annee` | 0.65 | 0.06 | -68.0% | 0.30 | 100% | 1.39 | 0.3 | +19.9% · 0% | — · — |
| long | **buy & hold** | 0.86 | — | -75.0% | — | — | — | — | +43.5% | — |

6 configuration(s) sans aucun trade (indicateur jamais défini sur cette barre) : exclues du classement.

PBO par actif : NVDA 0.00, PLTR 0.05, BTCUSD 0.01, ETHUSD 0.44
