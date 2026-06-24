---
type: alpha_hypothesis
statut: hypothese
classe: [equity]
horizon: moyen_terme
facteur: insider
dsr: null
pbo: null
sharpe: null
maxdd: null
sources: ["[[paper_lakonishok_lee_2001]]"]
date_creation: 2026-06-24
---

# 🎯 Clusters d'achats d'initiés (SEC Form 4)

## Thèse (sens économique)
> Une **grappe** d'achats d'initiés signale une asymétrie d'information (les initiés savent) →
> dérive positive 1-3 mois. Peu encombré pour le retail (barrière = parser EDGAR).

## Implémentation
- `packages/data/sec_insiders.py` : `fetch_recent_form4()` (EDGAR full-text, sans clé, offline-safe)
  + `insider_cluster_score(filings, ticker, window)`.
- ⚠️ **Limite** : la full-text donne les DÉPÔTS, pas le code P(achat)/S(vente). Le score actuel mesure
  l'**activité** d'initiés (proxy). Distinguer achat/vente = parser le XML du Form 4 (**TODO** prioritaire).

## Résultats
- **À backtester** une fois le buy/sell discriminé. C'est le candidat le moins encombré.

## Verdict
HYPOTHÈSE — l'edge réel dépend du buy/sell (XML). Forte priorité de recherche.

## Liens
- Complémentaire de [[pead]].
