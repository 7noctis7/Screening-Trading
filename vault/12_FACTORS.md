# 12 — FACTORS

> Source de poids : `config/factors.yaml`. Calculateurs : `packages/ranking/factors.py`.
> Chaque facteur → valeur brute par actif → **z-score cross-sectional** → composite pondéré.

## Implémentés (techniques)
- **momentum** : rendement 12-1 (lookback 252j en excluant les 21 derniers) — capture la persistance.
- **trend** : écart cours / SMA longue (200j) — tendance établie.
- **low_vol** : − volatilité réalisée (63j) — l'anomalie low-vol.

## À venir (P1 fondamental — Module 6)
- **value** : EV/EBITDA, P/B, PER vs comparables sectoriels (normalisé secteur).
- **quality** : ROIC/ROE, marges, DuPont, dette nette/EBITDA, qualité du cash (accruals).
- **size** : capitalisation (cross-sectional).

## Règles
- Pondérations **dépendantes du régime** (override risk_off) **ET de la classe** :
  `class_applicability` retire value/quality pour forex/crypto (renormalisation du composite).
- Un facteur absent pour une classe = **poids retiré**, jamais une erreur.
- **Explicabilité** : chaque actif rangé porte la contribution de chaque facteur + la raison.
