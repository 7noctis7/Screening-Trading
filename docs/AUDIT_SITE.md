# 🔍 Audit du site — Quant Terminal (2026-06-17)

> Audit transversal **honnête** du terminal : pour chaque critère → **état actuel** (avec
> références `fichier:ligne`), **note /20** et **axes de correction / amélioration** priorisés
> (🔴 prioritaire · 🟠 utile · 🟢 confort). L'esprit du projet est respecté : pas de promesse
> de performance, le **Sharpe déflaté (DSR)** reste le juge de paix de tout « edge ».

| Critère | Note | Tendance |
|---|---|---|
| UI/UX design | **18/20** | ↗ |
| Fluidité & animations | **17/20** | ↗ |
| Minimalisme | **16/20** | → |
| Machine Learning | **15/20** | → |
| Finance (fondamentaux/valorisation) | **14/20** | ↗ |
| Trading (portefeuille/exécution) | **17/20** | → |
| Data | **15/20** | ↗ |
| Risk management | **18/20** | → |

**Global ≈ 16,3/20 vs référence institutionnelle · ≈ 19/20 en retail gratuit.**

---

## 1. 🎨 UI/UX design — 18/20
**État.** Système de design à variables CSS (`apps/web/app/globals.css`), thème clair/sombre
anti-flash (`layout.tsx`), cartes à élévation, focus-visible, ⌘K (`CommandPalette.tsx`), tables
triables/filtrables/CSV (`SortableTable.tsx`), charts pro (lightweight-charts + recharts),
charte « bull & bear » néon + réseau de points animé (`ParticlesBg.tsx`). Navigation ordonnée
selon le pipeline (`Nav.tsx` + `Pipeline.tsx`).

**Axes d'amélioration.**
- 🔴 **Cohérence des couleurs sémantiques** : vérifier que vert/rouge ne servent QUE P&L/risque
  (quelques `#22c55e`/`#f43f5e` en dur traînent dans les pages — centraliser sur `var(--pos/neg)`).
- 🟠 **Accessibilité (WCAG AA)** : audit contrastes du thème clair, `aria-label` sur les boutons-icônes
  (toggles de séries), navigation clavier complète des tableaux.
- 🟠 **États vides & erreurs** : homogénéiser `EmptyState`/`PageSkeleton` sur TOUTES les pages
  (certaines retournent `null`).
- 🟢 **Layouts sauvegardés** (colonnes visibles, séries actives) persistés en `localStorage`.

## 2. 🌀 Fluidité & animations — 17/20
**État.** Apparition douce des pages (`@keyframes fade`), halos dérivants + ken-burns photo,
particules canvas plafonnées (≤ 90 nœuds, `requestAnimationFrame`), `prefers-reduced-motion`
respecté partout. Graphiques `isAnimationActive={false}` pour éviter le jank au survol.

**Axes d'amélioration.**
- 🟠 **Budget de rendu** : la boucle de particules + recharts + lightweight-charts sur une même
  page peut coûter cher sur petite machine → couper les particules quand l'onglet est masqué
  (`document.hidden`) et baisser la densité sous 768 px.
- 🟠 **Transitions de route** : ajouter un fondu/skeleton inter-pages (Next App Router `loading.tsx`).
- 🟢 **Micro-interactions** : animation de tri des colonnes, compteurs `countUp` sur les KPI clés.

## 3. ◻️ Minimalisme — 16/20
**État.** Hiérarchie typographique nette, déférence (l'UI s'efface), `max-w` contraints. Mais la
densité d'information est forte (beaucoup de cartes/tableaux par page).

**Axes d'amélioration.**
- 🔴 **Progressive disclosure** : replier par défaut les analyses avancées (EVT, GARCH, ACP…)
  derrière un « Détails ▸ » — montrer l'essentiel d'abord.
- 🟠 **Réduire le bruit textuel** : certaines notes explicatives sont longues ; les déplacer dans
  des tooltips/`<details>`.
- 🟢 **Une « vue compacte » globale** (toggle densité) au-delà de la prop `dense` des tables.

## 4. 🤖 Machine Learning — 15/20
**État.** Pipeline solide et **anti-fuite** : CV purgée + embargo (`packages/ml/cv.py`),
triple-barrier (`labeling.py`), calibration Platt + Brier (`calibration.py`), conformal
(`conformal.py`), meta-labeling + sizing (`meta.py`), drift PSI (`drift.py`), HPO Optuna
(`hpo.py`), walk-forward (`backtest/ml_walkforward.py`).
**Réalité mesurée** : sur les backtests honnêtes, **IC ≈ 0 et DSR = 0%** → l'edge prédictif
n'est PAS prouvé. C'est correctement reporté (pas de data-mining).

**Axes d'amélioration.**
- 🔴 **Features à plus fort contenu** : les features actuelles (momentum/trend/RSI/vol) sont
  saturées. Tester : qualité fondamentale point-in-time, surprises de résultats (PEAD réel),
  microstructure, flux. C'est le seul vrai levier d'IC.
- 🟠 **Modèles séries temporelles** : `amazon/chronos` (HF) ou `river` (online learning) en option.
- 🟠 **Registre de modèles + garde-fou AUC** : refuser un ré-entraînement si AUC OOS < seuil.
- 🟢 **Importance des features SHAP** exposée dans l'onglet ML (interprétabilité).

## 5. 💰 Finance — fondamentaux & valorisation — 14/20
**État.** DCF (`valuation.py`), ratios, **Piotroski F-score complet YoY** + **Altman Z**
(`scoring.py`), doctrines investisseurs Graham/Fisher/Thiel/Schwab (`investor_scores.py`),
note technique + combinée. Providers : synthétique déterministe (par défaut), **FMP** et
**yfinance** (`QUANT_FUND=yf`). Bug « croissance identique » corrigé (`provider.get_prior`).

**Axes d'amélioration.**
- 🔴 **Données réelles par défaut** : le mode synthétique reste actif si aucune clé. Documenter et
  encourager `QUANT_FUND=yf` (767 actifs, gratuit) → la note finance passe 14→17.
- 🔴 **Point-in-time des fondamentaux** : pour un backtest fondamental crédible, il faut l'historique
  des publications (FMP statements + dates de publication) — aujourd'hui le N-1 est reconstruit.
- 🟠 **Révisions d'analystes & estimations** (FMP) → facteur « revisions » classique.
- 🟢 **Comparables sectoriels (peers)** et premium/discount relatif affiné.

## 6. 📈 Trading — portefeuille & exécution — 17/20
**État.** Construction risk-parity/HRP/min-var/IVP (`portfolio/optimize.py`), no-trade band +
DD-target (`construction.py`), turnover/capacité (`capacity.py`), algos TWAP/VWAP
(`execution/algos.py`), réconciliation + TCA (`reconciliation.py`, `tca.py`), exécuteur paper
Alpaca/Bitmart dry-run. Backtests : conviction PIT, multi-stratégie, frontière de levier.

**Axes d'amélioration.**
- 🟠 **Réconciliation live réelle** : brancher la boucle sur l'état broker en continu (aujourd'hui
  surtout cible↔cible). Nécessite clés `.env`.
- 🟠 **Modèle de coûts par actif** : spread/impact calibrés par classe (crypto ≠ actions).
- 🟢 **Optimisation des frais** (rebalancement fiscalement/coût-conscient, seuils dynamiques).

## 7. 🗄️ Data — 15/20
**État.** Lecteur `YAHOO.db` avec auto-détection de schéma, mode **mixte** (réel/synthétique)
affiché, mapping crypto/forex→Yahoo, rapport qualité (NaN/outliers/staleness, `data_health.py`),
couverture par classe d'actifs, **FRED** (macro chiffrée) + **FMI** (projections, sans clé),
news RSS (`QUANT_NEWS=1`).

**Axes d'amélioration.**
- 🔴 **Cron quotidien actif** : `make cron` documenté mais à activer (crontab/launchd) pour des
  prix frais sans intervention.
- 🟠 **Élargir la couverture réelle** (→ 929 actifs) en complétant les alias tickers manquants.
- 🟠 **Stores persistants** (DuckDB/Parquet bronze/silver/gold) plutôt que recalcul en mémoire.
- 🟢 **Validation de schéma à l'ingestion** (Great Expectations-like) + alertes staleness.

## 8. 🛡️ Risk management — 18/20
**État.** VaR/CVaR + Cornish-Fisher (`risk_advanced.py`), EWMA, **GARCH(1,1)** (`garch.py`),
**EVT POT+GPD** 99,9% (`evt.py`), **backtest de VaR Kupiec + Christoffersen** (`var_backtest.py`),
risque factoriel ACP (`factor_risk.py`), **PSR/DSR** (`psr.py`), budget de risque (MCTR/PCTR),
limites de concentration HHI (`risk/limits.py`), stress-tests + hedging (`scenarios.py`),
fragilité Taleb (skew/kurtosis/tail ratio), risque de liquidité, kill-switch drawdown.

**Axes d'amélioration.**
- 🟠 **Modèle factoriel commercial** (Barra-like) — au-delà de l'ACP maison.
- 🟠 **VaR intraday / horizon multiple** et backtests de VaR roulants exposés dans l'UI.
- 🟢 **Scénarios définis par l'utilisateur** (chocs custom) + corrélations conditionnelles en stress.

---

## 🎯 Priorités transverses (si je ne devais garder que 5)
1. 🔴 **Brancher les données réelles par défaut** (`QUANT_FUND=yf`, cron quotidien, élargir mapping)
   → débloque Finance + Data + crédibilité des backtests.
2. 🔴 **Features ML à plus fort contenu** (fondamental PIT, surprises de résultats) → seul vrai
   levier d'IC ; tout le reste de la stack ML est déjà en place.
3. 🔴 **Point-in-time des fondamentaux** (FMP statements + dates) → backtests fondamentaux crédibles.
4. 🟠 **Progressive disclosure** (replier l'avancé) → minimalisme + lisibilité.
5. 🟠 **Réconciliation live réelle + coûts par actif** → fiabilité du sleeve trading.

> ⚠️ **Plafond honnête** : un IC ≈ 0 et un DSR = 0% signifient qu'aucun edge prédictif n'est
> prouvé à ce stade. La valeur du terminal est dans la **discipline** (risk-parity, no-trade band,
> DD-target, anti-fuite) et la **lisibilité**, pas dans une promesse de surperformance. Passer le
> plafond 19→20 par catégorie suppose des données payantes (tick temps réel, fondamentaux PIT
> complets, facteur Barra) — pas seulement du code.
