# 10 — BACKTEST RESULTS

> Résultats datés + hash de config + version données (DVC à venir).
> **Toujours OOS / walk-forward + deflated Sharpe.** Un Sharpe in-sample ne vaut rien.

## Méthodologie (S5)
- **Walk-forward** : fenêtres roulantes train→test (warm-up pour indicateurs valides),
  sélection params in-sample, évaluation **out-of-sample**, segments OOS concaténés.
- **Deflated Sharpe (DSR)** : corrige le multiple testing (nb total d'essais = grille ×
  fenêtres). Règle : ne passer en prod qu'avec **DSR élevé** (~>0.95). PSR en complément.

## Journal des runs
| Date | Stratégie | Données | Fenêtres | Essais | OOS Sharpe | PSR | DSR | Verdict |
|---|---|---|---|---|---|---|---|---|
| S5 (démo) | ma_crossover | synthétique seed=7 (4 actifs, 7 ans) | 16 | 64 | 0.46 | 0.90 | 0.00 | NON significatif |

> ⚠️ Données SYNTHÉTIQUES : aucune conclusion d'edge. Le DSR=0 confirme juste que le
> pipeline ne fabrique pas d'alpha. Refaire sur données réelles (yfinance/FMP) ensuite.
