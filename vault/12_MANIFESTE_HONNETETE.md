# 12 — Manifeste d'honnêteté méthodologique

> *« Dans un marché saturé de promesses non-falsifiables, le seul actif crédible est celui qui
> publie ses propres limites. »* — Verdict du Conseil d'Administration Suprême.

## Le principe (notre « wedge »)
Quant Terminal **n'a pas d'alpha directionnel prouvé** — et nous l'affichons. Nos calibrations
(`make calibrate-preset`) donnent un **Sharpe Déflaté (DSR) ≈ 0** : statistiquement, aucune
sur-performance robuste après correction du biais de sélection (multiple testing). C'est la vérité,
et c'est **notre différenciation**.

## Ce que nous revendiquons (vrai et mesuré)
- **Gestion du risque** : drawdown réduit ~2× vs équipondéré sur le backtest preset
  reproductible (`make backtest-preset` : preset −9,0 % vs équipondéré −23,3 %, run 2026-06-23,
  cf. `vault/04_JOURNAL.md`). *(Aucun chiffre de stress non reproductible n'est revendiqué ici.)*
- **Béta cœur assumé** : 50 % QQQ + satellite risk-managed (ADR-0023). Pas de prétention d'oracle.
- **Anti-overfitting** : gate $DSR>0 \wedge PBO<0.5$, CV purgée/embargo (López de Prado), fuite de
  données détectée et corrigée (le « 6,9 % d'alpha » initial était un artefact de look-ahead).
- **Auditabilité** : lignage de données (`packages/data/lineage.py`), manifeste de reproductibilité
  (`make repro`), gate de publication anti « site muet » (`scripts/check_build.py`).
- **Survivorship partiellement corrigé** : seed curée de délistés/acquis/**faillis** (incl. SIVB,
  FRC, SBNY) + détection des barres périmées (`make ingest-delisted`). Résidu assumé : la
  correction complète exigerait des *vintages* point-in-time de l'univers (non gratuits) → les
  backtests longs restent lus comme légèrement optimistes.
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

## Registre des hypothèses alt-data testées (2026-06) — 7 négatifs propres
Pipeline honnête appliqué (event-study → placebo → coûts → DSR → PBO). **Un négatif documenté
vaut un positif** : il ferme une impasse au lieu de vendre un mirage.

| Hypothèse | Méthode | Verdict |
|---|---|---|
| PEAD large-cap | event-study panier, placebo | ❌ p=0,209 |
| PEAD small/mid | event-study ✅ p=0,019 **mais** backtest net | ❌ Sharpe 0,20 · DSR 0 · **PBO 0,76** |
| Insider Form 4 (large + small) | achats nets, dé-chevauchés, vs SPY | ❌ p≥0,55 (le t=8 brut = autocorrélation) |
| Funding crypto | fade, z causal, placebo | ❌ p=0,16 (t=-3,4 trompeur : queues épaisses) |
| On-chain TVL/MCap (crypto) | event-study cross-actif, placebo | ❌ p≈0,18 (4 actifs) ; fees/MCap *non testable* (data) |
| Fear & Greed contrarian (BTC) | fade z causal, placebo, 1000j Binance | ❌ p=0,905 (t=0,38 : aucun signal) |
| Cassure de canal (BTC) | placebo ✅ p=0,039 → **gate complet** | ❌ **DSR 0 · PBO 0,88 · sabotage échoue** (rétention −11,7) — cas d'école du faux positif |

**Leçon transverse :** plusieurs fois un **t-stat/p-value spectaculaire** (insider t=8, funding
t=-3,4, **cassure de canal p=0,039**) a été **désamorcé en aval** — le placebo gonflé par les
fenêtres qui se chevauchent, puis le **DSR** (déflation tests multiples), le **PBO** (overfit des
params) et le **sabotage** (coûts réels) qui achèvent le faux positif. La cassure de canal est
l'exemple parfait : **placebo ✅ mais DSR 0 / PBO 0,88 / sabotage −11,7**. Le gate à 4 étages sépare
la recherche de l'illusion. **Conclusion : pas d'alpha directionnel exploitable dans la data gratuite
testée → on optimise la variance, pas l'espérance.**
