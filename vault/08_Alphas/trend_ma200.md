---
type: alpha_hypothesis
statut: promu
classe: [equity, etf]
horizon: moyen_terme
facteur: trend
dsr: 0.0
pbo: 0.5
sharpe: 2.1
maxdd: -0.09
sources: []
date_creation: 2026-06-23
---

# 🎯 Tendance MA200

## Thèse (sens économique)
> Persistance des tendances de fond ; au-dessus de la MM200 = régime haussier. Sert surtout de
> **gate de régime** (réduit l'exposition en marché baissier), pas d'alpha autonome.

## Implémentation
- Feature : `close / mean(close[-200:]) - 1` · `packages/ranking/factors.py::Trend`
- Aussi utilisé en porte de régime dans `preset_backtest._regime_mult`.

## Résultats (réel)
- **DSR ≈ 0** · contribue à la baisse du MaxDD (-9 %) en A/B krach.

## Verdict
**Promu comme gate de risque.** Pas d'alpha directionnel prouvé.

## Liens
- Redondant avec [[momentum_12_1]] (corrélation élevée) → ne pas sur-pondérer les deux.
