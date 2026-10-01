# Résultats de simulation multi-horizons

> `python -m packages.backtest.grid_runner` · 2026-09-30 20:30 UTC · source **vps-crypto** · grille `multi-horizons-2026-09-30` [900737b716db] · depuis 2018-01-01 · 8 actifs : KAVA/USDT, ROSE/USDT, ETH/USDT, ENA/USDT, SHIB/USDT, EOS/USDT, FTM/USDT, GMX/USDT

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

## Court terme — timeframe daily (384 essais · fréquences jour, semaine)

| Horizon | Configuration (stratégie · sortie · fréquence) | Sharpe | DSR méd. | MaxDD | Calmar | Win | PF | Turnover/an | Rend. 1 an(s) · bat B&H |
|---|---|---|---|---|---|---|---|---|---|
| court | `ma_crossover · signal · jour` | 0.60 | 0.05 | -82.7% | 0.26 | 36% | 1.18 | 6.7 | -10.7% · 70% |
| court | `ma_crossover · tp_3atr · jour` | 0.54 | 0.04 | -82.4% | 0.19 | 59% | 1.03 | 19.3 | -15.1% · 71% |
| court | `ma_crossover · suiveur_3atr · jour` | 0.50 | 0.02 | -85.7% | 0.11 | 38% | 1.03 | 18.1 | -25.4% · 63% |
| court | `ma_crossover · signal · semaine` | 0.50 | 0.03 | -81.1% | 0.15 | 31% | 1.15 | 6.6 | -13.1% · 72% |
| court | `ma_crossover · suiveur_3atr · semaine` | 0.37 | 0.02 | -82.4% | 0.03 | 36% | 1.01 | 14.9 | -24.7% · 62% |
| court | **buy & hold** | 0.29 | — | -95.0% | — | — | — | — | -38.9% |

PBO par actif : KAVA/USDT 0.81, ROSE/USDT 0.30, ETH/USDT 0.55, ENA/USDT 0.25, SHIB/USDT 0.48, EOS/USDT 0.53, FTM/USDT 0.17, GMX/USDT 0.20

## Moyen terme — timeframe daily (192 essais · fréquences mois, trimestre)

| Horizon | Configuration (stratégie · sortie · fréquence) | Sharpe | DSR méd. | MaxDD | Calmar | Win | PF | Turnover/an | Rend. 3 an(s) · bat B&H | Rend. 5 an(s) · bat B&H |
|---|---|---|---|---|---|---|---|---|---|---|
| moyen | `ma_crossover · signal · mois` | 0.57 | 0.04 | -82.9% | 0.18 | 30% | 1.18 | 4.8 | -15.4% · 76% | -7.1% · 41% |
| moyen | `ma_crossover · tp_3atr · mois` | 0.53 | 0.05 | -71.3% | 0.18 | 59% | 1.14 | 9.4 | -2.9% · 92% | -1.4% · 60% |
| moyen | `ma_crossover · tendance_mm200 · mois` | 0.24 | 0.04 | -77.4% | -0.03 | 35% | 0.98 | 1.5 | +0.4% · 86% | +8.1% · 86% |
| moyen | `ma_crossover · tendance_mm200 · trimestre` | 0.18 | 0.01 | -72.5% | -0.12 | 37% | 0.04 | 0.8 | -11.0% · 88% | -1.4% · 92% |
| moyen | `momentum_12_1 · signal · trimestre` | 0.17 | 0.05 | -89.4% | -0.14 | 27% | 0.36 | 0.7 | -6.2% · 66% | +1.3% · 68% |
| moyen | **buy & hold** | 0.29 | — | -95.0% | — | — | — | — | -30.0% | -19.7% |

PBO par actif : KAVA/USDT 0.25, ROSE/USDT 0.37, ETH/USDT 0.85, ENA/USDT 0.17, SHIB/USDT 0.96, EOS/USDT 0.71, FTM/USDT 0.17, GMX/USDT 0.10

## Long terme — timeframe daily (64 essais · fréquences trimestre, annee)

| Horizon | Configuration (stratégie · sortie · fréquence) | Sharpe | DSR méd. | MaxDD | Calmar | Win | PF | Turnover/an | Rend. 5 an(s) · bat B&H | Rend. 10 an(s) · bat B&H |
|---|---|---|---|---|---|---|---|---|---|---|
| long | `momentum_12_1 · signal · trimestre` | 0.17 | 0.02 | -89.4% | -0.14 | 27% | 0.36 | 0.7 | +1.3% · 68% | — · — |
| long | `momentum_12_1 · signal · annee` | 0.15 | 0.04 | -90.2% | -0.15 | 0% | 0.00 | 0.3 | -13.8% · 45% | — · — |
| long | `momentum_12_1 · tendance_mm200 · trimestre` | -0.01 | 0.00 | -72.9% | -0.16 | 0% | 0.00 | 0.8 | -14.6% · 87% | — · — |
| long | `tendance_mm200 · signal · trimestre` | -0.01 | 0.00 | -88.8% | -0.20 | 22% | 0.07 | 1.4 | -18.7% · 48% | — · — |
| long | `tendance_mm200 · tendance_mm200 · trimestre` | -0.01 | 0.00 | -88.8% | -0.20 | 22% | 0.07 | 1.4 | -18.7% · 48% | — · — |
| long | **buy & hold** | 0.29 | — | -95.0% | — | — | — | — | -19.7% | — |

PBO par actif : KAVA/USDT 0.65, ROSE/USDT 0.40, ETH/USDT 0.51, ENA/USDT 0.34, SHIB/USDT 0.75, EOS/USDT 0.75, FTM/USDT 0.20, GMX/USDT 0.18

## Court terme — timeframe weekly (192 essais · fréquences semaine)

| Horizon | Configuration (stratégie · sortie · fréquence) | Sharpe | DSR méd. | MaxDD | Calmar | Win | PF | Turnover/an | Rend. 1 an(s) · bat B&H |
|---|---|---|---|---|---|---|---|---|---|
| court | `rsi_reversion · suiveur_3atr · semaine` | 0.15 | 0.03 | -35.1% | 0.16 | 60% | 1.60 | 0.5 | +0.0% · 71% |
| court | `rsi_reversion · signal · semaine` | 0.11 | 0.03 | -35.1% | 0.00 | 100% | 0.36 | 0.3 | +0.0% · 67% |
| court | `rsi_reversion · tp_3atr · semaine` | 0.11 | 0.03 | -35.1% | 0.00 | 100% | 0.36 | 0.3 | +0.0% · 67% |
| court | `momentum_12_1 · tp_3atr · semaine` | 0.03 | 0.01 | -77.7% | -0.17 | 50% | 0.65 | 3.5 | -15.2% · 58% |
| court | `momentum_12_1 · suiveur_3atr · semaine` | 0.01 | 0.02 | -77.6% | -0.17 | 36% | 0.39 | 3.4 | -11.7% · 62% |
| court | **buy & hold** | 0.29 | — | -94.4% | — | — | — | — | -37.4% |

9 configuration(s) sans aucun trade (indicateur jamais défini sur cette barre) : exclues du classement.

PBO par actif : KAVA/USDT 0.62, ROSE/USDT 0.94, ETH/USDT 0.17, ENA/USDT 1.00, SHIB/USDT 0.92, EOS/USDT 0.74, FTM/USDT 0.58, GMX/USDT 0.02

## Moyen terme — timeframe weekly (192 essais · fréquences mois, trimestre)

| Horizon | Configuration (stratégie · sortie · fréquence) | Sharpe | DSR méd. | MaxDD | Calmar | Win | PF | Turnover/an | Rend. 3 an(s) · bat B&H | Rend. 5 an(s) · bat B&H |
|---|---|---|---|---|---|---|---|---|---|---|
| moyen | `momentum_12_1 · signal · trimestre` | 0.24 | 0.05 | -80.7% | -0.06 | 32% | 0.32 | 0.7 | -6.2% · 61% | +3.9% · 73% |
| moyen | `momentum_12_1 · tp_3atr · mois` | 0.15 | 0.07 | -80.1% | -0.06 | 42% | 0.80 | 2.5 | -3.8% · 74% | -2.2% · 56% |
| moyen | `momentum_12_1 · tp_3atr · trimestre` | 0.11 | 0.03 | -75.8% | -0.11 | 33% | 0.64 | 1.2 | -6.2% · 55% | -1.9% · 42% |
| moyen | `momentum_12_1 · signal · mois` | 0.05 | 0.08 | -84.4% | -0.13 | 33% | 0.11 | 0.8 | -18.4% · 66% | -11.7% · 54% |
| moyen | `smclxtp · signal · mois` | 0.00 | 0.05 | -65.1% | -0.15 | 0% | 0.00 | 0.3 | -14.1% · 66% | -11.6% · 66% |
| moyen | **buy & hold** | 0.29 | — | -94.4% | — | — | — | — | -32.8% | -19.8% |

12 configuration(s) sans aucun trade (indicateur jamais défini sur cette barre) : exclues du classement.

PBO par actif : KAVA/USDT 0.63, ROSE/USDT 0.81, ETH/USDT 0.13, ENA/USDT 0.86, SHIB/USDT 0.80, EOS/USDT 0.52, FTM/USDT 0.31, GMX/USDT 0.92

## Long terme — timeframe weekly (64 essais · fréquences trimestre, annee)

| Horizon | Configuration (stratégie · sortie · fréquence) | Sharpe | DSR méd. | MaxDD | Calmar | Win | PF | Turnover/an | Rend. 5 an(s) · bat B&H | Rend. 10 an(s) · bat B&H |
|---|---|---|---|---|---|---|---|---|---|---|
| long | `momentum_12_1 · signal · trimestre` | 0.24 | 0.09 | -80.7% | -0.06 | 32% | 0.32 | 0.7 | +3.9% · 73% | — · — |
| long | `momentum_12_1 · signal · annee` | 0.15 | 0.09 | -88.4% | -0.16 | 0% | 0.00 | 0.3 | -13.4% · 44% | — · — |
| long | **buy & hold** | 0.29 | — | -94.4% | — | — | — | — | -19.8% | — |

6 configuration(s) sans aucun trade (indicateur jamais défini sur cette barre) : exclues du classement.

PBO par actif : KAVA/USDT 0.61, ROSE/USDT 1.00, ETH/USDT 0.11, ENA/USDT 1.00, SHIB/USDT 0.54, EOS/USDT 0.74, FTM/USDT 0.12, GMX/USDT 1.00

## Moyen terme — timeframe monthly (192 essais · fréquences mois, trimestre)

| Horizon | Configuration (stratégie · sortie · fréquence) | Sharpe | DSR méd. | MaxDD | Calmar | Win | PF | Turnover/an | Rend. 3 an(s) · bat B&H | Rend. 5 an(s) · bat B&H |
|---|---|---|---|---|---|---|---|---|---|---|
| moyen | `momentum_12_1 · tp_3atr · trimestre` | 0.17 | 0.21 | -73.7% | -0.07 | 25% | 0.83 | 1.4 | +6.7% · 61% | +2.0% · 65% |
| moyen | `momentum_12_1 · signal · trimestre` | 0.08 | 0.21 | -77.8% | -0.11 | 30% | 0.36 | 0.7 | +5.9% · 61% | +4.6% · 65% |
| moyen | `momentum_12_1 · tp_3atr · mois` | -0.01 | 0.20 | -77.5% | -0.19 | 37% | 0.32 | 1.3 | -10.7% · 62% | -14.4% · 50% |
| moyen | `momentum_12_1 · signal · mois` | -0.11 | 0.19 | -80.4% | -0.22 | 33% | 0.10 | 0.9 | -19.2% · 62% | -16.6% · 50% |
| moyen | **buy & hold** | 0.30 | — | -93.4% | — | — | — | — | -30.3% | -19.0% |

20 configuration(s) sans aucun trade (indicateur jamais défini sur cette barre) : exclues du classement.

PBO par actif : KAVA/USDT 0.73, ROSE/USDT 0.88, ETH/USDT 0.29, ENA/USDT —, SHIB/USDT 0.96, EOS/USDT 0.92, FTM/USDT 0.27, GMX/USDT 1.00

## Long terme — timeframe monthly (64 essais · fréquences trimestre, annee)

| Horizon | Configuration (stratégie · sortie · fréquence) | Sharpe | DSR méd. | MaxDD | Calmar | Win | PF | Turnover/an | Rend. 5 an(s) · bat B&H | Rend. 10 an(s) · bat B&H |
|---|---|---|---|---|---|---|---|---|---|---|
| long | `momentum_12_1 · signal · trimestre` | 0.08 | 0.12 | -77.8% | -0.11 | 30% | 0.36 | 0.7 | +4.6% · 65% | — · — |
| long | `momentum_12_1 · signal · annee` | 0.04 | 0.16 | -85.2% | -0.16 | 0% | 0.00 | 0.3 | -13.8% · 38% | — · — |
| long | **buy & hold** | 0.30 | — | -93.4% | — | — | — | — | -19.0% | — |

6 configuration(s) sans aucun trade (indicateur jamais défini sur cette barre) : exclues du classement.

PBO par actif : KAVA/USDT 0.78, ROSE/USDT 1.00, ETH/USDT 0.19, ENA/USDT —, SHIB/USDT 0.98, EOS/USDT 1.00, FTM/USDT 0.25, GMX/USDT 1.00
