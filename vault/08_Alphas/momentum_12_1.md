---
type: alpha_hypothesis
statut: promu
classe: [equity, etf, crypto]
horizon: swing
facteur: momentum
dsr: 0.01
pbo: 0.5
sharpe: 2.44
maxdd: -0.09
sources: ["[[paper_jegadeesh_titman_1993]]"]
date_creation: 2026-06-23
---

# 🎯 Momentum 12-1 cross-sectionnel

## Thèse (sens économique)
> Sous-réaction puis sur-réaction comportementale : les actifs forts le restent ~3-12 mois
> (Jegadeesh-Titman). On exclut le dernier mois (skip 21 j) pour éviter le reversal court terme.

## Implémentation
- Feature : `mom_12_1 = close[-21] / close[-252] - 1` · `packages/ranking/factors.py::Momentum`
- Univers : equity/ETF/crypto liquide (filtre `dollar_volume`).

## Résultats (réel, `make calibrate-preset`)
- **DSR ≈ 0.01** (≈ 0) · PBO ~0.5 · Sharpe brut 2.44 · MaxDD -9 %.
- Stationnarité : prix → `min_ffd` requis (cf. `adf_stat`).

## Verdict
**Promu comme composante de RISQUE/β, pas comme alpha** : le DSR≈0 dit qu'il n'y a pas d'edge
directionnel robuste après déflation multi-essais. Valeur réelle = réduction du drawdown.

## Liens
- Très corrélé à [[trend_ma200]] (même direction) → attention au double comptage.
