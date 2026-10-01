# Résultats de simulation multi-horizons

> `python -m packages.backtest.grid_runner` · 2026-09-30 20:28 UTC · source **vps-quotidien** · grille `multi-horizons-2026-09-30` [900737b716db] · depuis 2015-01-01 · 12 actifs : HIG, FSLR, MGM, GD, INTU, RR, ITW, EWD, CB, GPC, EXC, SNPS

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

## Court terme — timeframe daily (576 essais · fréquences jour, semaine)

| Horizon | Configuration (stratégie · sortie · fréquence) | Sharpe | DSR méd. | MaxDD | Calmar | Win | PF | Turnover/an | Rend. 1 an(s) · bat B&H |
|---|---|---|---|---|---|---|---|---|---|
| court | `smclxtp · suiveur_3atr · semaine` | 0.43 | 0.07 | -34.1% | 0.18 | 48% | 1.36 | 11.3 | +8.4% · 35% |
| court | `ma_crossover · tendance_mm200 · jour` | 0.42 | 0.06 | -40.5% | 0.19 | 28% | 1.93 | 5.2 | +6.4% · 20% |
| court | `tendance_mm200 · signal · jour` | 0.41 | 0.10 | -43.8% | 0.15 | 28% | 1.71 | 8.1 | +5.6% · 21% |
| court | `tendance_mm200 · tendance_mm200 · jour` | 0.41 | 0.10 | -43.8% | 0.15 | 28% | 1.71 | 8.1 | +5.6% · 21% |
| court | `ma_crossover · tendance_mm200 · semaine` | 0.40 | 0.08 | -40.0% | 0.15 | 34% | 1.95 | 2.7 | +6.3% · 21% |
| court | **buy & hold** | 0.52 | — | -53.3% | — | — | — | — | +14.3% |

PBO par actif : HIG 0.47, FSLR 0.14, MGM 0.94, GD 0.82, INTU 0.73, RR 0.18, ITW 0.62, EWD 0.77, CB 0.95, GPC 0.19, EXC 0.50, SNPS 0.42

## Moyen terme — timeframe daily (288 essais · fréquences mois, trimestre)

| Horizon | Configuration (stratégie · sortie · fréquence) | Sharpe | DSR méd. | MaxDD | Calmar | Win | PF | Turnover/an | Rend. 3 an(s) · bat B&H | Rend. 5 an(s) · bat B&H |
|---|---|---|---|---|---|---|---|---|---|---|
| moyen | `momentum_12_1 · tp_3atr · trimestre` | 0.49 | 0.45 | -42.0% | 0.19 | 88% | 2.17 | 4.3 | +5.1% · 26% | +5.3% · 6% |
| moyen | `smclxtp · tp_3atr · mois` | 0.42 | 0.32 | -40.2% | 0.20 | 76% | 1.80 | 6.9 | +7.9% · 26% | +10.4% · 10% |
| moyen | `ma_crossover · tendance_mm200 · mois` | 0.41 | 0.27 | -37.9% | 0.14 | 44% | 2.35 | 1.7 | +6.3% · 22% | +8.0% · 14% |
| moyen | `tendance_mm200 · tp_3atr · mois` | 0.40 | 0.29 | -34.5% | 0.14 | 76% | 1.49 | 7.5 | +5.8% · 14% | +8.7% · 10% |
| moyen | `tendance_mm200 · signal · mois` | 0.40 | 0.31 | -38.6% | 0.14 | 43% | 2.05 | 1.8 | +5.2% · 18% | +5.6% · 4% |
| moyen | **buy & hold** | 0.52 | — | -53.3% | — | — | — | — | +11.3% | +11.7% |

PBO par actif : HIG 0.45, FSLR 0.03, MGM 0.27, GD 0.70, INTU 0.86, RR 0.40, ITW 0.41, EWD 0.81, CB 0.43, GPC 0.44, EXC 0.50, SNPS 0.74

## Long terme — timeframe daily (96 essais · fréquences trimestre, annee)

| Horizon | Configuration (stratégie · sortie · fréquence) | Sharpe | DSR méd. | MaxDD | Calmar | Win | PF | Turnover/an | Rend. 5 an(s) · bat B&H | Rend. 10 an(s) · bat B&H |
|---|---|---|---|---|---|---|---|---|---|---|
| long | `tendance_mm200 · signal · annee` | 0.35 | 0.35 | -51.4% | 0.10 | 100% | 0.15 | 0.3 | +6.3% · 3% | +6.4% · 0% |
| long | `tendance_mm200 · tendance_mm200 · annee` | 0.35 | 0.35 | -51.4% | 0.10 | 100% | 0.15 | 0.3 | +6.3% · 3% | +6.4% · 0% |
| long | `momentum_12_1 · tendance_mm200 · annee` | 0.33 | 0.35 | -51.4% | 0.09 | 67% | 0.25 | 0.3 | +3.0% · 0% | +5.2% · 0% |
| long | `tendance_mm200 · signal · trimestre` | 0.32 | 0.36 | -44.5% | 0.08 | 50% | 1.46 | 1.0 | +1.5% · 1% | +4.9% · 0% |
| long | `tendance_mm200 · tendance_mm200 · trimestre` | 0.32 | 0.36 | -44.5% | 0.08 | 50% | 1.46 | 1.0 | +1.5% · 1% | +4.9% · 0% |
| long | **buy & hold** | 0.52 | — | -53.3% | — | — | — | — | +11.7% | +12.6% |

PBO par actif : HIG 0.89, FSLR 0.03, MGM 1.00, GD 0.84, INTU 0.65, RR 0.73, ITW 0.46, EWD 0.17, CB 0.56, GPC 0.46, EXC 0.54, SNPS 0.84

## Court terme — timeframe weekly (288 essais · fréquences semaine)

| Horizon | Configuration (stratégie · sortie · fréquence) | Sharpe | DSR méd. | MaxDD | Calmar | Win | PF | Turnover/an | Rend. 1 an(s) · bat B&H |
|---|---|---|---|---|---|---|---|---|---|
| court | `rsi_reversion · signal · semaine` | 0.34 | 0.09 | -20.2% | 0.20 | 100% | 2.67 | 0.3 | +0.0% · 31% |
| court | `momentum_12_1 · suiveur_3atr · semaine` | 0.34 | 0.09 | -39.6% | 0.14 | 53% | 1.39 | 5.0 | +5.3% · 26% |
| court | `rsi_reversion · suiveur_3atr · semaine` | 0.33 | 0.08 | -22.6% | 0.14 | 75% | 2.80 | 0.5 | +0.0% · 31% |
| court | `momentum_12_1 · signal · semaine` | 0.32 | 0.07 | -46.9% | 0.10 | 56% | 1.37 | 2.9 | +6.3% · 17% |
| court | `rsi_reversion · tp_3atr · semaine` | 0.31 | 0.08 | -20.2% | 0.17 | 100% | 2.67 | 0.4 | +0.0% · 31% |
| court | **buy & hold** | 0.50 | — | -48.7% | — | — | — | — | +13.7% |

PBO par actif : HIG 0.51, FSLR 0.13, MGM 0.46, GD 0.67, INTU 0.43, RR 0.89, ITW 0.83, EWD 0.21, CB 0.44, GPC 0.35, EXC 0.67, SNPS 0.56

## Moyen terme — timeframe weekly (288 essais · fréquences mois, trimestre)

| Horizon | Configuration (stratégie · sortie · fréquence) | Sharpe | DSR méd. | MaxDD | Calmar | Win | PF | Turnover/an | Rend. 3 an(s) · bat B&H | Rend. 5 an(s) · bat B&H |
|---|---|---|---|---|---|---|---|---|---|---|
| moyen | `momentum_12_1 · tp_3atr · trimestre` | 0.35 | 0.29 | -44.8% | 0.12 | 73% | 2.24 | 2.3 | +3.3% · 9% | +4.6% · 0% |
| moyen | `smclxtp · tp_3atr · trimestre` | 0.35 | 0.33 | -39.2% | 0.15 | 86% | 4.12 | 1.2 | +4.2% · 19% | +5.7% · 3% |
| moyen | `momentum_12_1 · tp_3atr · mois` | 0.33 | 0.28 | -43.5% | 0.10 | 71% | 1.67 | 3.2 | +4.4% · 8% | +1.5% · 0% |
| moyen | `tendance_mm200 · signal · mois` | 0.32 | 0.18 | -43.0% | 0.10 | 25% | 0.38 | 0.3 | +1.0% · 6% | +6.1% · 0% |
| moyen | `tendance_mm200 · tendance_mm200 · mois` | 0.32 | 0.18 | -43.0% | 0.10 | 25% | 0.38 | 0.3 | +1.0% · 6% | +6.1% · 0% |
| moyen | **buy & hold** | 0.50 | — | -48.7% | — | — | — | — | +11.2% | +12.0% |

PBO par actif : HIG 0.63, FSLR 0.44, MGM 0.56, GD 0.53, INTU 0.09, RR 0.64, ITW 0.70, EWD 0.31, CB 0.54, GPC 0.32, EXC 0.15, SNPS 0.31

## Long terme — timeframe weekly (96 essais · fréquences trimestre, annee)

| Horizon | Configuration (stratégie · sortie · fréquence) | Sharpe | DSR méd. | MaxDD | Calmar | Win | PF | Turnover/an | Rend. 5 an(s) · bat B&H | Rend. 10 an(s) · bat B&H |
|---|---|---|---|---|---|---|---|---|---|---|
| long | `momentum_12_1 · signal · trimestre` | 0.31 | 0.42 | -45.9% | 0.09 | 67% | 4.81 | 0.7 | +3.5% · 0% | +4.7% · 0% |
| long | `momentum_12_1 · signal · annee` | 0.26 | 0.36 | -50.1% | 0.06 | 50% | 0.46 | 0.4 | +4.2% · 0% | +3.9% · 0% |
| long | `tendance_mm200 · signal · trimestre` | 0.24 | 0.21 | -40.1% | 0.09 | 33% | 0.26 | 0.2 | +0.8% · 0% | +4.3% · 0% |
| long | `tendance_mm200 · tendance_mm200 · trimestre` | 0.24 | 0.21 | -40.1% | 0.09 | 33% | 0.26 | 0.2 | +0.8% · 0% | +4.3% · 0% |
| long | `momentum_12_1 · tendance_mm200 · trimestre` | 0.17 | 0.15 | -39.9% | 0.04 | 33% | 0.00 | 0.2 | +0.7% · 0% | +2.9% · 0% |
| long | **buy & hold** | 0.50 | — | -48.7% | — | — | — | — | +12.0% | +12.3% |

3 configuration(s) sans aucun trade (indicateur jamais défini sur cette barre) : exclues du classement.

PBO par actif : HIG 0.66, FSLR 0.27, MGM 0.52, GD 0.98, INTU 0.18, RR 0.80, ITW 0.88, EWD 0.42, CB 0.37, GPC 0.57, EXC 0.70, SNPS 0.43

## Moyen terme — timeframe monthly (288 essais · fréquences mois, trimestre)

| Horizon | Configuration (stratégie · sortie · fréquence) | Sharpe | DSR méd. | MaxDD | Calmar | Win | PF | Turnover/an | Rend. 3 an(s) · bat B&H | Rend. 5 an(s) · bat B&H |
|---|---|---|---|---|---|---|---|---|---|---|
| moyen | `momentum_12_1 · signal · mois` | 0.35 | 0.19 | -41.2% | 0.14 | 54% | 1.79 | 1.3 | +4.5% · 8% | +3.6% · 1% |
| moyen | `momentum_12_1 · tp_3atr · mois` | 0.34 | 0.19 | -41.2% | 0.13 | 59% | 2.04 | 1.8 | +4.5% · 12% | +3.6% · 3% |
| moyen | `momentum_12_1 · signal · trimestre` | 0.33 | 0.17 | -42.5% | 0.11 | 67% | 2.04 | 0.7 | +4.4% · 5% | +2.6% · 0% |
| moyen | `momentum_12_1 · tp_3atr · trimestre` | 0.30 | 0.19 | -42.5% | 0.09 | 57% | 1.94 | 1.3 | +5.2% · 15% | +3.1% · 0% |
| moyen | **buy & hold** | 0.54 | — | -40.4% | — | — | — | — | +11.8% | +11.4% |

20 configuration(s) sans aucun trade (indicateur jamais défini sur cette barre) : exclues du classement.

PBO par actif : HIG 0.24, FSLR 1.00, MGM 0.91, GD 0.14, INTU 0.23, RR 0.94, ITW 0.13, EWD 0.23, CB 0.21, GPC 0.56, EXC 0.24, SNPS 0.00

## Long terme — timeframe monthly (96 essais · fréquences trimestre, annee)

| Horizon | Configuration (stratégie · sortie · fréquence) | Sharpe | DSR méd. | MaxDD | Calmar | Win | PF | Turnover/an | Rend. 5 an(s) · bat B&H | Rend. 10 an(s) · bat B&H |
|---|---|---|---|---|---|---|---|---|---|---|
| long | `momentum_12_1 · signal · trimestre` | 0.33 | 0.25 | -42.5% | 0.11 | 67% | 2.04 | 0.7 | +2.6% · 0% | +4.6% · 0% |
| long | `momentum_12_1 · signal · annee` | 0.29 | 0.17 | -44.5% | 0.07 | 50% | 0.00 | 0.3 | +2.9% · 0% | +4.9% · 0% |
| long | **buy & hold** | 0.54 | — | -40.4% | — | — | — | — | +11.4% | +12.5% |

6 configuration(s) sans aucun trade (indicateur jamais défini sur cette barre) : exclues du classement.

PBO par actif : HIG 0.54, FSLR 0.38, MGM 1.00, GD 0.46, INTU 0.31, RR 0.97, ITW 0.38, EWD 0.45, CB 0.25, GPC 0.59, EXC 0.36, SNPS 0.00
