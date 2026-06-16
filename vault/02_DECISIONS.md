# 02 — DECISIONS (ADR)

> 1 entrée par choix structurant. Format : contexte → décision → conséquences.

## ADR-0001 — Stack & architecture de fondation
**Date :** session 0
**Statut :** accepté

**Contexte.** Le projet doit rester maintenable après des centaines de mises à jour
et permettre d'ajouter stratégies/indicateurs/sources/facteurs sans casser le cœur.

**Décision.**
- **Monorepo** `apps/` + `packages/` + `config/` + `vault/` + `tests/`.
- **`packages/core` = domaine pur, ZÉRO dépendance externe** (dataclasses + Enum stdlib).
  Interdiction d'y importer pandas/requests/fastapi/etc.
- **Architecture en plugins** via un `Registry` générique + décorateur d'auto-enregistrement.
- **Config-driven** : tout paramètre métier en YAML (`config/`), rien en dur.
- **Event bus interne** : découplage signal → risque → exécution → journal.
- **Outils** : Python 3.11+, uv, ruff, mypy, pytest ; FastAPI (back) ; Next.js (front).
- **Stockage** : DuckDB+Parquet (OHLCV/features), PostgreSQL/SQLite+SQLAlchemy (relationnel), ArcticDB (ticks).
- **Paper trading par défaut** ; aucun ordre réel sans feu vert explicite.

**Conséquences.**
- (+) Domaine testable en isolation, parité backtest↔live facilitée, ajouts non intrusifs.
- (+) Le test `test_registry.py` formalise la règle « 1 plugin = 1 fichier ».
- (−) Un peu de cérémonie initiale (interfaces) avant le premier résultat visible.
- Deps ajoutées **par groupe** (`pyproject` extras) au fil de la roadmap, pas en bloc.

## ADR-0002 — Indicateurs groupés par famille
**Décision.** Plutôt qu'un fichier pour chaque indicateur (des dizaines de fichiers
de 10 lignes), regrouper par famille (`trend.py`, `momentum.py`, `volatility.py`),
**1 classe = 1 indicateur**, toutes auto-enregistrées. Reste sous 400 lignes/fichier.
**Conséquence.** Ajouter un indicateur = ajouter une classe dans le bon fichier famille,
sans toucher au moteur. Conforme à l'esprit « 1 responsabilité ».

## ADR-0003 — Broker simulé partagé backtest ↔ live
**Décision.** `SimBroker` implémente l'interface `Broker` commune. Le moteur de
backtest et le futur paper-live consomment la MÊME interface → parité garantie.
**Conséquence.** Passer en paper-live = remplacer `SimBroker` par un `AlpacaBroker`
implémentant la même interface, sans changer la stratégie ni le risk engine.

## ADR-0004 — Sizer plafonné à la limite d'exposition, risk engine = backstop
**Décision.** Le sizer dimensionne DANS les limites d'exposition ; le risk engine
reste un backstop dur à droit de veto (défense en profondeur).
**Conséquence.** Comportement sain et redondant : même si un sizer mal réglé sur-
dimensionne, le veto bloque. Démontré par les tests `test_risk` + `test_engine`.

## ADR-0005 — Déterminisme : jamais `hash()` builtin pour seeder
**Contexte.** Le provider synthétique seedait via `hash(symbol)` → résultats de
backtest non reproductibles entre runs (PYTHONHASHSEED randomisé par process).
**Décision.** Tout seed dérivé d'une string passe par `hashlib.sha256` (stable).
Reproductibilité = priorité #1 ; un test (`test_reproducibility`) verrouille la propriété.
**Conséquence.** Même backtest = même résultat, indépendamment de l'environnement.

## ADR-0006 — Storage : SQLite maintenant, DuckDB+Parquet en cible prod
**Décision.** Implémenter le repository OHLCV sur **SQLite stdlib** (testable offline,
zéro dépendance) avec couches bronze/silver, clé `(symbol,timeframe,ts)` + UPSERT
idempotent. La cible prod (gros volumes/colonnaire) est **DuckDB+Parquet**, branchée
plus tard via la MÊME interface `BarsRepository` sans toucher aux consommateurs.
**Timeframe canonique = daily** pour le socle (cf. 08_DATA_MODEL) ; 1h/4h en surcouche
pour l'intraday/crypto. **Conséquence.** Pipeline data testable dès maintenant, montée
en charge sans refonte.

## ADR-0007 — Pas de LLM/agent dans le chemin chaud
**Décision.** Aucun agent IA dans data→indicateurs→screening→ranking→sizing→risque→
exécution (déterminisme, backtestabilité, pas d'hallucination où l'argent est en jeu,
rate-limits des tiers gratuits). LLM uniquement **aux bords** : revue experte rédigée
à partir des métriques **calculées** (jamais inventées), sentiment-news comme **feature**
(FinBERT, pas un chat), synthèse de recherche, et l'agent développeur. **Conséquence.**
Un seul agent qui *construit* du code déterministe > une nuée d'agents *dans la boucle*.

## ADR-0008 — Univers : source-driven + snapshots datés (pas de tickers en dur)
**Contexte.** Demande : CAC40/SP500/Nasdaq/NYSE/LSE/SBF120/Italie/Japon/Chine/Corée/
Pays-Bas + top100 crypto/ETF + top20 forex/commodities/indices (~milliers de titres).
**Décision.** NE PAS coder les tickers à la main (hallucination + péremption + survivorship).
1 source = 1 plugin (`static` CSV seed offline ; `wikipedia`/`nasdaq_trader`/`coingecko`
online). `UniverseBuilder` enchaîne, dédoublonne `(symbol,venue)`, persiste un **snapshot
daté** (membership point-in-time → anti survivorship-bias). Config déclarative `universe.yaml`.
**Conséquence.** Offline = ~325 (seeds exacts) ; en ligne = milliers, à jour, reproductibles
par snapshot. Listings non-US complets (JPX/KRX/Borsa/SSE) = extension `exchange_listing`
documentée (couverts pour l'instant par les constituants d'indices via Wikipédia).

## ADR-0009 — Rebuild d'univers MENSUEL (cadence-aware + scheduler)
**Décision.** `rebuild_cadence_days: 30` dans `universe.yaml`. `build_universe.py` est
cadence-aware (skip si snapshot < 30j, `--force` pour forcer). Planification :
`scripts/scheduler.py` (APScheduler, cron mensuel 1er du mois 02:00 UTC) OU cron système.
Chaque rebuild conserve un **snapshot daté** (point-in-time). **Conséquence.** L'univers
se met à jour tout seul une fois par mois ; l'historique de composition est préservé.

## ADR-0010 — Dédoublonnage par SYMBOLE (priorité = ordre des sources)
**Décision.** Le builder dédoublonne par symbole normalisé (upper/strip), pas par
`(symbol,venue)` : un même titre vu dans plusieurs sources (AAPL dans S&P500 + Nasdaq100
+ Russell + listings US) n'apparaît qu'**une fois**, la 1re source déclarée gagnant
(meilleures métadonnées). `duplicates_removed` rapporté. **Conséquence.** Zéro doublon
d'actif. Limite connue : résolution cross-listing fine (BRK.B vs BRK-B inter-conventions)
relève d'un mapping FIGI/ISIN — amélioration future.

## ADR-0011 — Russell 1000/3000 via holdings iShares (IWB/IWV)
**Décision.** Pas de liste Russell propre sur Wikipédia (trop volumineuse) → on lit les
**holdings iShares** (IWB=Russell 1000, IWV=Russell 3000), source gratuite et faisant
autorité, parser tolérant au préambule CSV. **Conséquence.** Constituants Russell exacts
et à jour à chaque rebuild.

## ADR-0012 — Feature store (gold) : cohérence backtest ↔ live (anti-skew)
**Décision.** Couche GOLD = `FeatureStore` (SQLite) clé `(symbol,timeframe,ts,name)`.
Indicateurs matérialisés point-in-time depuis SILVER via `materialize_indicators`
(config `features.yaml`). La MÊME computation/lecture sert backtest et live → pas de
training/serving skew. NaN de warm-up non stockés. **Conséquence.** Features
reproductibles, partagées ; test prouve store == recalcul. Cible prod : Feast/DuckDB
via la même API.

## ADR-0013 — Validation : walk-forward + deflated Sharpe (stdlib)
**Décision.** `WalkForwardRunner` : sélection params in-sample → évaluation OOS roulante
(avec warm-up). `statistics.py` : PSR + **Deflated Sharpe** (Bailey/López de Prado) via
`statistics.NormalDist` (aucune dépendance). Le DSR corrige le **multiple testing** : on
compte tous les essais (grille × fenêtres) et on déflate le seuil. **Conséquence.** Un
backtest "joli" non robuste est démasqué (DSR≈0 sur quasi-random après 64 essais).
Règle : ne passer en prod qu'au-delà d'un DSR élevé.

## ADR-0014 — Providers réels via wrappers (fallback/cache/rate-limit) + backend pluggable
**Décision.** Brancher les sources réelles SANS toucher aux consommateurs : `yfinance`
(OHLCV, normalisation `df_to_bars` pure/testée), `FMPFundamentalsProvider` (Financials,
parser `build_financials` pur/testé). Wrappers composables : `FallbackProvider` (essaie
plusieurs sources), `CachingProvider` (mémoïse + persiste silver), `RateLimitedProvider`
(quota, horloge injectable). Backend OHLCV pluggable via `make_bars_repository(sqlite|duckdb)`.
**Conséquence.** Le fetch réseau vit dans son adaptateur ; toute la LOGIQUE (fallback,
cache, rate-limit, parsing, normalisation) est testée offline. Passage SQLite↔DuckDB+Parquet
sans refonte (drop-in, même interface). `scripts/verify_real_data.py` valide en ligne.

## ADR-0015 — Macro point-in-time : MacroStore vintage + délai de publication
**Décision.** `MacroStore` (SQLite) stocke (series, obs_date, value, realtime_start).
`as_of(t)` ne retourne que ce qui était CONNU à t (realtime_start ≤ t), dernière révision
connue, période la plus récente → logique ALFRED. FRED/ALFRED réel via `FredProvider`
(parser `parse_observations` testé). Surprises éco = réalisé vs consensus (z). Cartographie
macro→actifs en config (`macro_impact.yaml`) → exposition + inclinaisons facteurs/classes.
Classifieur de cycle (`MacroRegimeClassifier`) : courbe 2s10s + ISM + chômage + VIX.
**Conséquence.** Zéro fuite du futur dans les features macro (impératif ML). Régime
quotidien point-in-time qui pilote exposition, pondérations et activation de stratégies.

## ADR-0016 — Exécution paper Alpaca + moteur live (parité) + idempotence/réconciliation
**Décision.** `AlpacaBroker` implémente l'interface `Broker` (PAPER par défaut), mappers purs
testés, réseau isolé. `LiveTradingEngine` réutilise les MÊMES Strategy/Sizer/RiskEngine/
Broker/Journal que le backtest, en streaming (step par barre) → **parité backtest↔paper↔live**.
Sécurité : retries **idempotents** (client_id ; SimBroker ne re-remplit pas), **kill-switch**
vérifié à chaque pas, **réconciliation** broker↔interne (`reconcile` + alerte). PAPER par
défaut, jamais de réel sans feu vert. **Conséquence.** Une stratégie validée OOS tourne en
paper sans réécriture ; les retries sont sûrs ; toute divergence est détectée.

## ADR-0017 — ML : triple-barrier, meta-labeling, CV purgée, champion/challenger
**Décision.** Module `packages/ml` (López de Prado) : labeling **triple-barrière** + **meta-
labeling** (séparer sens/taille) ; **PurgedKFold** (purge des labels chevauchants + embargo)
= la SEULE CV honnête en finance ; **frac-diff** (stationnarité + mémoire) ; `FeatureBuilder`
point-in-time (technique gold + macro `as_of`) → zéro fuite ; modèles : `LogitModel` numpy
(baseline sans dépendance) + adaptateurs sklearn/xgboost ; **gouvernance champion/challenger**
(promotion seulement si bat l'OOS + barrière de risque) + `ModelRegistry` (MLflow en prod).
**Conséquence.** Boucle d'amélioration sûre. Sur synthétique, OOS ~50% (aucun alpha fabriqué).

## ADR-0018 — API FastAPI (contrat) + front Next.js (consommateur), payloads testés
**Décision.** Le front ne contient AUCUNE logique : il consomme l'API. Les **builders de
payloads** (`apps/api/payloads.py`) sont des fonctions pures (totaux, P&L, exposition,
contributions de facteurs, rebase benchmarks) **testées offline**. `snapshot.py` assemble
l'état complet depuis un run synthétique (source offline) ; en prod, les routes liront le
live. Front : Next.js + TS + Tailwind, tokens partagés avec `11_DESIGN_SYSTEM.md`. Aperçu
HTML statique rendu depuis les vraies données (ouvrable sans build). **Conséquence.**
Contrat API garanti par les tests ; design visible immédiatement ; séparation stricte UI/domaine.

## ADR-0019 — Moteur analytique portefeuille (relatif, risque, corrélation, revue)
**Décision.** `packages/portfolio` étendu (maths pures, testées) : mesures relatives au
benchmark (beta/alpha/TE/IR/R²/up-down capture, esprit CFA/CIPM) ; VaR/CVaR historique &
paramétrique (FRM) ; corrélation + clustering single-linkage (anti fausse-diversification) ;
attribution du P&L ; stress test + Monte Carlo (proba de ruine) ; **revue experte** ancrée
EXCLUSIVEMENT sur les métriques calculées (aucun chiffre inventé) + score de santé.
Exposé via l'API (`/api/portfolio` → bloc `analysis`) et rendu (aperçu + pages Next.js).
**Conséquence.** Le risque de portefeuille (au-delà du trade) est mesuré, expliqué, visible.

## ADR-0020 — Alertes multi-canal (event bus → moteur → sinks), hiérarchisées & anti-spam
**Décision.** `AlertEngine` émet vers des `sinks` (InMemory/Console testables ; Telegram/
Discord réseau, formateur `format_message` pur/testé). Sévérité INFO/WARNING/CRITICAL ;
chaque canal a un seuil. **Throttle** (TTL + dedup_key) anti-spam. Handlers (1/type) abonnés
à l'event bus (`register_on_bus`) : régime, kill-switch, rejet risque, qualité données, fill,
divergence broker↔DB. Toutes les alertes tracées (audit). Un canal HS ne bloque pas les autres.
**Conséquence.** Les événements critiques (kill-switch, divergence) remontent immédiatement.

## ADR-0021 — Excellence opérationnelle (drift, audit, télémétrie, backup, tear sheets)
**Décision.** `ml/drift.py` (PSI : dérive features/prédictions → réentraînement) ; `common/audit.py`
(audit trail append-only rejouable : décision + contexte features/régime/modèle) ; `common/
telemetry.py` (compteurs/gauges/timers → dashboard santé) ; `storage/backup.py` (sauvegarde/
restauration SQLite native) ; `reporting/tearsheet.py` (tear sheet HTML + **PDF reportlab**).
Drift branché aux alertes. **Conséquence.** Traçabilité conformité, détection de dérive,
sauvegardes testées, reporting partageable — le passage prototype → niveau pro.
