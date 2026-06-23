# 12 — Manifeste d'honnêteté méthodologique

> *« Dans un marché saturé de promesses non-falsifiables, le seul actif crédible est celui qui
> publie ses propres limites. »* — Verdict du Conseil d'Administration Suprême.

## Le principe (notre « wedge »)
Quant Terminal **n'a pas d'alpha directionnel prouvé** — et nous l'affichons. Nos calibrations
(`make calibrate-preset`) donnent un **Sharpe Déflaté (DSR) ≈ 0** : statistiquement, aucune
sur-performance robuste après correction du biais de sélection (multiple testing). C'est la vérité,
et c'est **notre différenciation**.

## Ce que nous revendiquons (vrai et mesuré)
- **Gestion du risque** : Max DD divisé par ~2 en A/B krach (-53,6 % → -31,7 %).
- **Béta cœur assumé** : 50 % QQQ + satellite risk-managed (ADR-0023). Pas de prétention d'oracle.
- **Anti-overfitting** : gate $DSR>0 \wedge PBO<0.5$, CV purgée/embargo (López de Prado), fuite de
  données détectée et corrigée (le « 6,9 % d'alpha » initial était un artefact de look-ahead).
- **Auditabilité** : lignage de données (`packages/data/lineage.py`), manifeste de reproductibilité
  (`make repro`), gate de publication anti « site muet » (`scripts/check_build.py`).
- **Souveraineté & coût** : 0 €/$ d'infra (Mac éteint, Actions + Pages + cache HF gratuits).

## Ce que nous ne ferons jamais
- Vendre un signal d'investissement (paper par défaut ; **pas un conseil financier**).
- Afficher un Sharpe non déflaté comme une preuve d'edge.
- Cacher une métrique défavorable.

## Le test scientifique permanent
Pour tout signal candidat $s$, sous la filtration $\mathcal{F}_t$ :
$$\mathbb{E}[r_{t+1}\mid \mathcal{F}_t,\, s] \approx 0 \;\Rightarrow\; \text{on optimise } \mathbb{V}[\cdot]\text{, pas } \mathbb{E}[\cdot].$$
Aucun facteur n'entre en production sans franchir le gate DSR/PBO. La qualité du **processus** est
le produit ; la survie (antifragilité) est l'objectif ; l'honnêteté est la marque.
