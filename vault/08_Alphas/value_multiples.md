---
type: alpha_hypothesis
statut: en_test
classe: [equity]
horizon: moyen_terme
facteur: value
dsr: 0.0
pbo: 0.6
sharpe: null
maxdd: null
sources: []
date_creation: 2026-06-23
---

# 🎯 Value (multiples vs secteur)

## Thèse (sens économique)
> Décote des multiples (P/E, EV/EBITDA) vs le secteur → prime de valeur (Fama-French HML).
> Sector-neutral.

## Implémentation
- `packages/fundamentals/factors.py::ValueFactor`.

## Résultats
- **EN TEST** : à valider en point-in-time (anti look-ahead fondamental).

## Verdict
À confirmer avant promotion.

## Liens
- Couplé à [[quality]] (QARP).
