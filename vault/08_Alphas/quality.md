---
type: alpha_hypothesis
statut: en_test
classe: [equity]
horizon: moyen_terme
facteur: quality
dsr: 0.0
pbo: 0.6
sharpe: null
maxdd: null
sources: []
date_creation: 2026-06-23
---

# 🎯 Quality (ROIC / marge / FCF)

## Thèse (sens économique)
> Les entreprises de qualité (rentabilité élevée, FCF stable) sur-performent (Novy-Marx).
> Sector-neutral pour éviter le biais sectoriel.

## Implémentation
- `packages/fundamentals/factors.py::QualityFactor` (ROIC + marge brute + conversion FCF).

## Résultats
- **EN TEST** : nécessite des fondamentaux **point-in-time réels** (vintages) pour conclure —
  risque de look-ahead/survivorship fondamental tant que ce n'est pas garanti.

## Verdict
À valider point-in-time avant promotion. Loguer l'essai : `make log-alpha`.

## Liens
- Complémentaire de [[value_multiples]] (qualité × valorisation = « quality at a reasonable price »).
