---
type: alpha_hypothesis
statut: hypothese        # hypothese | en_test | rejete | promu
classe: [equity]         # equity | etf | crypto | forex | commodity
horizon: swing           # daily | swing | moyen_terme
facteur: ""              # momentum | trend | low_vol | value | quality | ...
dsr: null                # Sharpe déflaté (rempli APRÈS backtest) — gate : >0.5 pour « robuste »
pbo: null                # Probability of Backtest Overfitting (<0.5 souhaité)
sharpe: null
maxdd: null
sources: []              # [[paper_xxx]] reliés
date_creation: ""
---

# 🎯 {{titre}}

## Thèse (sens économique)
> *Pourquoi cet alpha devrait exister ? Quel comportement de marché l'explique ?*

## Implémentation (idée → algorithme)
- Feature / signal :
- Univers / horizon :
- Code : `packages/...`

## Résultats (preuve, pas intuition)
- DSR : · PBO : · Sharpe : · MaxDD :
- Walk-forward OOS : · Monte Carlo trades :
- Stationnarité (ADF / min_ffd) :

## Verdict
- [ ] DSR > 0.5 ET PBO < 0.5 → **promu**
- [ ] sinon → **rejeté** ou **en_test** (et on logue l'essai : `make log-alpha`)

## Liens
- Facteurs corrélés : (relier les notes pour repérer les doublons d'idées)
