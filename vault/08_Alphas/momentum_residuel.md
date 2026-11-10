---
type: alpha_hypothesis
statut: en_test
classe: [equity, etf]
horizon: moyen_terme
facteur: residual_momentum
dsr: null
pbo: null
sharpe: null
maxdd: null
sources: ["Blitz, Huij & Martens (2011), Residual Momentum", "Gutierrez & Prinsky (2007)"]
date_creation: 2026-11-10
---

# 🎯 Momentum résiduel (marché retiré)

## Thèse (sens économique)
> Le momentum de prix mélange le mouvement propre du titre et son exposition au marché.
> Seule la première part est une information sur le titre ; la seconde charge le haut du
> classement en bêta et casse aux retournements.

## Implémentation
- Facteur `residual_momentum` (`packages/ranking/momentum_residuel.py`), statut
  `CANDIDATE_UNCALIBRATED`, **hors** `config/factors.yaml` : aucun ordre n'en dépend.
- Score = somme des résidus (régression sur le marché équipondéré, 36 mois) sur 12 mois en
  sautant le dernier, divisée par leur écart-type. Aucun paramètre ajusté.
- Le score mesure « le titre fait mieux que sa propre habitude », pas « le titre monte » :
  une dérive permanente est retirée avec la constante.

## Résultats
- **UNCALIBRATED** — aucune mesure réelle. Essai figé :
  `config/essais/2026-11-10_momentum_residuel.yaml` ; lancer `make labo-momentum-residuel`.

## Verdict
EN TEST — règle écrite avant la mesure (ADR-0222) : facteur retenu si l'écart d'IC apparié
face au momentum 12-1 est positif (p < 0,05), stable sur les deux moitiés et aux deux
horizons ; stratégie promouvable seulement après le gate complet.

## Risques à surveiller en paper (si le facteur est retenu)
- Rotation par rééquilibrage et coût réel (`make tca`, ≥ 20 ordres) contre le coût modèle.
- Écart d'IC glissant face au témoin : arrêt si négatif sur 6 mois.
- Bêta du top-12 contre l'univers (il doit rester proche de 1 : c'est la promesse).
- Part des titres écartés pour historique incomplet (36 mois exigés : biais vers les anciens).
