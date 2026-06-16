# Rapport d'audit — Screening-Trading

> Auditeur senior (architecture logicielle, design UI/UX, trading quantitatif, ML).
> Périmètre : monorepo `packages/` + `apps/api` (FastAPI) + `apps/web` (Next.js) + preview autonome `apps/web/preview/build_interactive.py`.
> Date : 2026-06-16. Méthode : lecture du code source (chemins `file:line` cités).

## Synthèse exécutive

Le dépôt est **structurellement excellent** pour un projet quant personnel/OSS : cœur sans dépendances, système de plugins par registry, point-in-time (vintages ALFRED) réel, parité backtest↔live, CV purgée + embargo et deflated Sharpe corrects (López de Prado). C'est nettement au-dessus de la moyenne.

Les risques principaux ne sont **pas** dans la rigueur quant mais dans : (1) un **front Next.js inaccessible et fragile** (a11y nulle, aucune gestion d'erreur), (2) une **double implémentation du design** (preview HTML vs Next.js) qui diverge, (3) un **écart entre le README et la réalité** (providers FMP/Alpaca data **inexistants**, « Kelly » non implémenté en tant que tel), (4) une **API sans contrats** (aucun schéma Pydantic, cache figé qui ne sera jamais « live »), (5) des **fallbacks de dépendances optionnelles incomplets** (reportlab). Avant tout passage en capital réel, plusieurs hypothèses de réalisme du backtest (gap risk, vol gelée à l'entrée) doivent être documentées/corrigées.

---

## 1. DESIGN / UX

### Constats
- **Double design qui diverge.** La palette/typo est répliquée dans 4 sources non synchronisées : `apps/web/preview/build_interactive.py:26` (CSS inline), `apps/web/tailwind.config.ts:6-8`, `apps/web/lib/tokens.ts:4-8`, `apps/web/app/globals.css`. `lib/tokens.ts` n'est **jamais importé** dans les `.tsx` (token mort). Le `tearsheet.py` redéfinit encore la même palette (`packages/reporting/tearsheet.py:11`).
- **Accessibilité quasi nulle.** Aucun attribut ARIA, aucun focus visible, aucune navigation clavier. Onglets en `div.onclick` sans `role="tab"`/`aria-selected` (`build_interactive.py` JS d'onglets) ; lignes de tableau cliquables sans `role`/`tabindex` ; `globals.css` ne déclare aucun `focus-visible:ring`. `Nav.tsx` utilise `<Link>` (bien) mais sans état focus.
- **Gestion d'erreur API absente.** `apps/web/lib/api.ts` : `get<T>()` lève une erreur jamais catchée ; aucune `error.tsx`/`loading.tsx` Next.js, aucun error boundary, aucun retry/timeout → écran blanc si l'API tombe. États « chargement » vs « vide » vs « erreur » indistincts (chaque page : `if (!data) return <div>Chargement…</div>`).
- **Responsivité incomplète.** Grilles qui sautent d'étages (`grid-cols-2 md:grid-cols-4`, sans `sm:`), 6 colonnes de métriques écrasées (`apps/web/app/trades/page.tsx`). `Nav.tsx` en `flex-wrap` sans menu burger : 7 liens débordent sur 375px. Tables en `overflow-x-auto` + police `mono` (large) = UX mobile médiocre.
- **« Premium » partiel.** `darkMode:"class"` activé mais `layout.tsx` force `class="dark"` en dur → pas de toggle, pas de mode clair. Micro-interactions présentes côté preview HTML (countUp, crosshair SVG) mais **absentes** du Next.js (Recharts seul). Charts divergents : SVG custom (preview) vs Recharts (web) → rendu et features (axes, grille, légende) non alignés.
- **API mock figée.** `apps/api/main.py:18-25` met en cache un **unique** snapshot synthétique (`_CACHE`) ; le front consomme cette structure en dur → la promesse « brancher l'état live » n'est pas câblée.

### Points forts
- Palette cohérente et sobre (vert/rouge réservés au P&L, bleu accent), look type terminal pro.
- Sémantique HTML correcte côté React (`<section>`, `<table>`, `<thead>`), navigation sticky + backdrop-blur.
- Heatmap de corrélation et courbe d'equity soignées ; React Query pour le cache (`useDashboard` refetch 15 s).
- Séparation propre du client API (`lib/api.ts`).

### Faiblesses / risques
- Produit annoncé « premium »/institutionnel mais **inaccessible** (échouerait un audit WCAG AA) et **fragile** (aucune robustesse réseau).
- Double maintenance design → tout changement doit être fait à 4 endroits (source de bugs visuels).
- Refetch asymétrique : dashboard rafraîchi, portfolio/screener figés.

### Recommandations
- **P0** Gérer les erreurs réseau : error boundary global, `error.tsx`/`loading.tsx` par route, retry + timeout dans `lib/api.ts`, messages humains (pas « API /dashboard: 500 »).
- **P0** Baseline a11y : `role/aria` sur onglets et lignes cliquables, `focus-visible:ring` global, navigation clavier (flèches sur onglets), test Lighthouse/axe ; menu burger mobile dans `Nav.tsx`.
- **P1** Source unique de tokens : générer `globals.css`/Tailwind depuis `lib/tokens.ts` ; faire générer la preview HTML à partir des **mêmes** tokens.
- **P1** États visuels distincts (skeletons via `<Suspense>`/`loading.tsx`) ; compléter les breakpoints (`sm:`) ; aspect ratio mini pour les charts mobiles.
- **P2** Unifier les charts (composant partagé ou converger sur Recharts) ; toggle dark/light ; micro-interactions (countUp animé) ; metadata/SEO Next.js.

---

## 2. ARCHITECTURE

### Constats
- **Plugins par registry, claim tenu.** `packages/core/registry.py` (decorator d'auto-enregistrement) + `Protocols` runtime-checkable (`packages/core/interfaces.py`). Stratégies, indicateurs, sizers s'enregistrent par décorateur. **Mais** la découverte dépend d'imports manuels dans les `__init__.py` : un fichier `@register` non importé devient invisible (pas d'erreur).
- **API sans contrats.** `apps/api/main.py` : 8 routes GET renvoyant `dict`, **aucun `response_model` Pydantic**, aucune validation, pas de doc OpenAPI typée. `apps/api/payloads.py`/`snapshot.py` sont des builders purs et testables (bon), mais sérialisent à la main (enum/datetime) sans schéma versionné. Le front est couplé en dur à la forme du snapshot → pas de backward-compat.
- **Providers data : écart README/réalité.** `packages/data/providers/` ne contient que `synthetic.py`, `yfinance_provider.py`, `wrappers.py`. **Aucun provider FMP ni Alpaca-data** (grep négatif). FRED existe (`packages/regime/fred_provider.py`) et Alpaca uniquement comme **broker** (`packages/execution/alpaca_broker.py`). Le README annonçant « providers synthetic/yfinance/FMP » est **inexact**.
- **Wrappers de robustesse solides.** `FallbackProvider`/`CachingProvider`/`RateLimitedProvider` (`packages/data/providers/wrappers.py`) avec horloge injectable → testables offline. Bonne base offline/online, mais peu de sources réelles à enchaîner faute de providers.
- **Reproductibilité.** Synthetic seedé de façon déterministe par symbole (SHA256→int), seeds explicites dans démos/tests, point-in-time partout. Solide.
- **Fallbacks de deps optionnelles inégaux.** ML : `LogitModel` numpy pur en fallback de sklearn/xgboost (`packages/ml/model.py`) — **excellent**. Reporting : `to_pdf()` importe `reportlab` **localement** dans la fonction (`packages/reporting/tearsheet.py:53`) — le module s'importe donc sans crash, mais l'appel échoue sans message clair si reportlab absent (pas de fallback « HTML-only » explicite). Config YAML : `pyyaml` gracieusement optionnel (`packages/common/config.py`) mais le dict chargé n'est **pas validé** (pas de schéma).
- **Stores hardcodés SQLite.** `macro_store`/`feature_store` n'ont pas d'interface abstraite swappable (contrairement à Broker/Provider) ; DuckDB/parquet annoncés mais peu exploités.

### Points forts
- Cœur sans dépendances ; couches `core ← adapters ← apps` respectées ; type hints stricts (mypy strict en config).
- Feature store anti training/serving skew ; medallion bronze/silver/gold ; qualité de données (pandera-like).
- Snapshot synthétique complet permettant de faire tourner toute la chaîne offline ; ~150 tests miroir de `packages/`.
- Zéro TODO/FIXME dans le code (dette explicite quasi nulle).

### Faiblesses / risques
- README survend l'état réel (providers FMP/Alpaca data, « tear sheets PDF » sans fallback) → confiance/repro affectées.
- API non versionnée et non typée → couplage front fragile, pas de tests d'intégration HTTP.
- Découverte de plugins fragile (oubli d'import silencieux).
- Cache snapshot figé (`_CACHE`) ne se rafraîchit jamais → « live » non câblé.

### Recommandations
- **P0** Aligner README et réalité : retirer/َmarquer « roadmap » les providers FMP/Alpaca-data et « Kelly » ; documenter que la PDF nécessite reportlab.
- **P0** Fallback gracieux reporting : envelopper l'import reportlab et retourner le HTML (ou message d'install clair) si absent.
- **P1** Contrats API Pydantic (`response_model` par route) + champ `version` dans les payloads + `TestClient` FastAPI dans la suite.
- **P1** Découverte auto des plugins (scan de répertoire) ; validation Pydantic des YAML de config.
- **P2** Interface de stockage abstraite (SQLite/DuckDB/Postgres) ; câbler un vrai état live derrière l'API (invalidation de `_CACHE`).

---

## 3. TRADING

### Constats
- **Anti-look-ahead respecté.** Indicateurs en avance pure avec warm-up `NaN` (RSI `packages/indicators/momentum.py`, EMA/SMA `trend.py`, ATR `volatility.py`). Le moteur ne passe aux stratégies qu'une fenêtre `bars[:t+1]` (`packages/backtest/engine.py:110-115`), jamais le futur.
- **Backtest event-driven cohérent, mais fills au close.** `engine.py` : fills au `bar.close`, coûts (frais+slippage) appliqués via `CostModel`, stop/target testés sur low/high, MFE/MAE et R-multiple tracés. **Limite** : fill instantané au close sans modèle next-open ni gestion de gap overnight → optimiste en cas de crack/gap.
- **Coûts simplistes mais présents dès le backtest.** `packages/execution/costs.py` : 5 bps frais + 2 bps slippage, constants. Pas d'impact dépendant de la taille/liquidité ni de spread variable ; ~14 bps aller-retour qui peuvent éroder fortement l'edge sur stratégies à forte rotation (à vérifier vs edge attendu).
- **Sizing.** `FixedFractional` correct (`risk = price - stop`, skip si ≤ 0). `VolTarget` (`packages/portfolio/sizing/vol_target.py`) : `capital_frac = min(max_frac, target_vol / vol_annualisée)` — formule saine, **bornée à 20 %**. Deux réserves : (a) la vol instrument est estimée par **ATR/price** sans ajuster la constante ATR≈1.4·σ → biais d'échelle ; (b) l'ATR est **gelé au signal** (`signal.features["atr"]`) → pas de redimensionnement si la vol explose après l'entrée. **« Kelly bridé » n'existe pas** en tant que sizer (seuls `fixed_fractional` et `vol_target`) malgré README/docstring.
- **Risque.** `RiskEngine` (`packages/risk/engine.py`) : kill-switch sur drawdown intraday (défaut 5 %), reset quotidien, veto une fois armé. Règles R:R (≥2), max positions (20), max exposition/actif (10 %). **Manque** : pas de veto VaR/CVaR portefeuille (les métriques existent en `portfolio/` mais ne sont pas branchées au moteur), pas de hard-stop anti-gap.
- **Régime.** Classifieur **rule-based à seuils en dur** (`packages/regime/classifier.py` : trend_window=200, vol_window=20, seuil vol annuelle 0.30) injecté dans le backtest. Le `MacroRegimeClassifier` point-in-time (vintages via `macro_store.as_of`) est correct mais **pas utilisé dans le backtest** par défaut. Macro→actifs implémenté mais non stress-testé.
- **Exécution.** SimBroker et AlpacaBroker (paper par défaut) partagent l'interface Broker → parité sim/paper/live. Idempotence par `client_id`, retries à backoff exponentiel, réconciliation broker↔interne. **Manque** côté Alpaca : gestion des partials/rejections et polling de statut (TIF=DAY uniquement).
- **Validation anti-overfit.** Walk-forward avec warm-up fourni avant chaque test (`packages/backtest/walkforward.py`) + Deflated/Probabilistic Sharpe **corrects** (`packages/backtest/statistics.py`, Bailey & López de Prado).

### Points forts
- Parité backtest↔live, anti-look-ahead, vintages point-in-time, coûts dès le backtest, WFO + DSR : socle quant rigoureux et rare à ce niveau.
- Réconciliation et idempotence côté exécution.
- Anti-survivorship via snapshots d'univers point-in-time.

### Faiblesses / risques
- Hypothèse « marché continu » (fills au close, vol gelée) → backtest optimiste sur événements extrêmes/gaps.
- Coûts forfaitaires : risque de surestimer l'edge net pour les stratégies actives.
- Régime fragile (seuils en dur, classifieur jamais backtesté seul, macro non branchée).
- Long-only, beta≈1 : pas de hedge → exposition pleine en krach.

### Recommandations
- **P0** Documenter/corriger le réalisme : modéliser le **fill next-open** et le **gap overnight** (clamp/hard-stop) dans `engine.py` ; test asserting que coûts RT < ~20 % de l'edge annuel.
- **P0** Lever l'incohérence README↔code : implémenter un vrai sizer Kelly bridé **ou** retirer la mention.
- **P1** Vol dynamique : recalculer la vol (vol réalisée 20 j ou ATR vivant) en live, redimensionnement/trailing ; ajuster la constante ATR→σ.
- **P1** Brancher VaR/CVaR comme règle de veto ; stress-test macro (récession + VIX haut ⇒ exposition réduite).
- **P1** Backtester le classifieur de régime seul ; utiliser `MacroRegimeClassifier` point-in-time dans le moteur.
- **P2** E2E Alpaca paper (1 semaine) : partials, rejections, statut, `reconcile().ok`, pas de doublons `client_id`. Envisager un hedge/beta-neutralité.

---

## 4. ML

### Constats
- **Labeling correct.** Triple-barrière (`packages/ml/labeling.py`) : profit/stop dynamiques (vol EWM) + horizon temps, label = 1re barrière touchée, signe du rendement si temps. Meta-labeling binaire (« le trade primaire aurait-il gagné ») bien séparé direction/taille.
- **CV purgée + embargo.** `packages/ml/cv.py` `PurgedKFold` : purge des échantillons train dont `[t0,t1]` chevauche la fenêtre test + embargo après test (López de Prado, AFML ch. 7). Implémentation fidèle. **Nuance** : l'embargo n'est appliqué qu'**après** la fenêtre test (`test_t1 + embargo`), pas avant ; acceptable mais asymétrique.
- **Pas de leakage de prétraitement.** Imputation + standardisation calculées **dans `fit`** (`packages/ml/model.py:21-28`, `SklearnModel` via `Pipeline`), et `purged_cv_score` instancie un modèle frais par fold (`packages/ml/evaluation.py:34`) → stats ré-estimées par fold, pas de fuite.
- **Features point-in-time.** `FeatureBuilder.build` lit le feature store à la barre + macro via `as_of` (`packages/ml/features.py:50-62`) → aucune valeur future. Frac-diff (poids tronqués, warm-up NaN) correct (AFML ch. 5).
- **Drift PSI correct.** `packages/ml/drift.py` : bins par quantiles de la référence, clip anti-zéro, seuils standards (0.1/0.25), flag global. Implémentation propre.
- **Gouvernance.** Champion/challenger avec marge minimale **et** barrière de risque (`packages/ml/governance.py`) ; registre in-memory. **Mais** : MLflow seulement évoqué (stub), pas de versioning d'artefacts/params réels, pas de reproductibilité d'expériences, et la logique champion/challenger n'est pas exercée dans les démos.
- **Évaluation limitée.** `purged_cv_score` ne renvoie que l'**accuracy** (`packages/ml/evaluation.py`) — métrique faible et trompeuse sur classes déséquilibrées (la démo montre ~36 % gagnants / 64 % stops) ; précision/rappel existent mais ne sont pas agrégés en CV, pas d'AUC/F1/log-loss, pas de lien explicite vers le DSR du backtest.
- **Trous de tests et fragilités.** La fonction centrale `purged_cv_score` n'a **pas de test dédié** (`tests/ml/`) ; `SklearnModel`/XGBoost ne sont pas testés (dépendance optionnelle non skipée). `frac_diff` (`packages/ml/features.py:31-38`) **échoue silencieusement** si la série contient des NaN (toute la sortie devient NaN), or `FeatureBuilder.build` peut produire des NaN (données manquantes) → casse silencieuse en aval.

### Points forts
- Stack López de Prado authentique (triple-barrière, meta-labeling, purged CV+embargo, frac-diff) — rare et bien fait.
- Fallback numpy pur (`LogitModel`) : ML toujours testable sans sklearn (dépendance optionnelle bien gérée).
- Anti-leakage de prétraitement et point-in-time cohérents avec le reste du système.
- Drift PSI exploitable opérationnellement.

### Faiblesses / risques
- MLOps embryonnaire : pas de registry/versioning réel, pas de tracking d'expériences ⇒ reproductibilité ML limitée, dérives non historisées.
- Évaluation centrée accuracy ⇒ risque de fausse confiance ; pas de pont métrique ML→performance économique.
- Champion/challenger non intégré au flux (gouvernance non exercée).
- `xgboost` (`make_model("xgboost")`) utilise `use_label_encoder` (déprécié dans les versions récentes) → risque de casse.

### Recommandations
- **P1** Élargir l'évaluation : AUC/F1/log-loss + précision/rappel agrégés en CV ; relier le score ML au **DSR**/perf backtest (utilité économique).
- **P1** MLOps : intégrer effectivement un registry (MLflow ou équivalent) avec params/metrics/artefacts + seed/versions de données ; historiser les décisions champion/challenger et les PSI.
- **P1** Ajouter un test dédié de `purged_cv_score` (non-fuite, bornes) et un garde-fou NaN dans `frac_diff` (erreur explicite ou imputation documentée).
- **P2** Embargo symétrique (avant et après la fenêtre test) ; tests conditionnels `skipif` pour SklearnModel/XGBoost ; corriger l'API XGBoost dépréciée (`use_label_encoder`) ; brancher le drift PSI sur un déclencheur de réentraînement réel.

---

## Feuille de route priorisée — Top 10

1. **(P0, UX)** Robustesse réseau du front : error boundary, `error.tsx`/`loading.tsx`, retry/timeout dans `lib/api.ts`.
2. **(P0, UX)** Baseline accessibilité : ARIA sur onglets/lignes, focus visible, navigation clavier, menu burger mobile.
3. **(P0, Archi)** Aligner README/docstrings sur la réalité : providers FMP/Alpaca-data inexistants, « Kelly » absent, PDF=reportlab requis.
4. **(P0, Archi)** Fallback gracieux du reporting PDF (HTML-only si reportlab absent) avec message clair.
5. **(P0, Trading)** Réalisme backtest : fill next-open + gestion du gap overnight (hard-stop/clamp) dans `engine.py`.
6. **(P0, Trading)** Test garde-fou des coûts : asserter coûts aller-retour < ~20 % de l'edge annuel attendu.
7. **(P1, Archi)** Contrats API Pydantic (`response_model`) + version de payload + tests `TestClient`.
8. **(P1, Trading)** Vol dynamique pour le sizing (recalcul live, ajustement ATR→σ) + veto VaR/CVaR au RiskEngine.
9. **(P1, Trading)** Backtester le classifieur de régime et utiliser le `MacroRegimeClassifier` point-in-time dans le moteur.
10. **(P1, ML)** Évaluation au-delà de l'accuracy (AUC/F1/log-loss, lien au DSR) + MLOps réel (registry/versioning, historisation drift & champion/challenger).

> Le système est de qualité « senior quant » sur le fond (rigueur anti-fuite, validation, parité sim/live). Les chantiers prioritaires concernent la **robustesse produit** (front, API, fallbacks) et la **véracité de la documentation**, puis le **réalisme d'exécution** avant tout capital réel.
