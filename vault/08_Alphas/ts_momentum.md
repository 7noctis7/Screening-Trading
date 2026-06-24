---
type: alpha_hypothesis
statut: hypothese
classe: [crypto]
horizon: moyen_terme
facteur: ts_momentum
dsr: null
pbo: null
sharpe: null
maxdd: null
sources: ["[[paper_moskowitz_tsmom_2012]]"]
date_creation: 2026-06-24
---

# 🎯 Momentum time-series (crypto)

## Thèse (sens économique)
> Marché crypto dominé par le retail, 24/7, arbitrage institutionnel lent → les tendances
> persistent plus longtemps qu'en actions (time-series momentum, Moskowitz-Ooi-Pedersen).

## Implémentation
- Facteur `ts_momentum` (`packages/ranking/factors.py::TSMomentum`) : `close[-1]/close[-window]-1`.
- Attention : annualisation crypto 365 j ; coûts crypto ~50 bps A/R (l'edge doit survivre).

## Résultats
- **À backtester** (DSR/PBO null). `make calibrate-preset` loguera le résultat.

## Verdict
HYPOTHÈSE — méfiance : le momentum pur risque le DSR≈0 ; l'edge dépend probablement de l'on-chain.

## Liens
- À combiner avec un signal on-chain (orthogonal) plutôt qu'isolé.
