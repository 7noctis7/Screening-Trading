---
type: alpha_hypothesis
statut: promu
classe: [equity, etf, crypto]
horizon: swing
facteur: low_vol
dsr: 0.0
pbo: 0.5
sharpe: 1.9
maxdd: -0.08
sources: []
date_creation: 2026-06-23
---

# 🎯 Anomalie basse volatilité

## Thèse (sens économique)
> Les actifs peu volatils sur-performent en risque ajusté (low-vol anomaly : contraintes de
> levier, biais loterie). On classe par volatilité réalisée inverse.

## Implémentation
- Feature : `-std(log-returns[-63:])` · `packages/ranking/factors.py::LowVol`

## Résultats (réel)
- **DSR ≈ 0** · améliore le Sharpe ajusté du risque, sans edge directionnel prouvé.

## Verdict
**Promu comme réducteur de risque.**

## Liens
- Anticorrélé au momentum en régime risk-on.
