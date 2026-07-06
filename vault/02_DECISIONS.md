# 02 — DECISIONS (ADR)

> 1 entrée par choix structurant. Format : contexte → décision → conséquences.

## ADR-0029 — Long-only = scope v1 assumé
**Date :** 2026-07-02 · **Statut :** accepté
Le système est **long-only** (`sim_broker.py:43` « v1 : pas de short » ; la vente ne fait que clôturer un long).
`Side.SHORT`/`SignalDirection.SHORT` existent dans les modèles mais **aucun chemin d'exécution short** n'a jamais
été implémenté — ce n'est **pas une régression**, c'est une frontière de scope v1 (audit adverse 02/07). Le short
reste hors-scope tant qu'il n'est pas explicitement rouvert par un ADR dédié.

## ADR-0028 — Journal de trades persistant : `SqliteTradeJournal` + flag `legacy` en couche storage
**Date :** 2026-07-02
**Statut :** accepté

**Contexte.** Le journal v1 (`TradeJournal`) était **en mémoire** → perdu à chaque process, et l'audit
full-review le donnait à **0/100** `features_snapshot` (P1-1) : MFE/MAE, expectancy, Kelly restaient
**UNCALIBRATED (N=0)**. Il fallait persister sans (a) mélanger le journal au cache prix régénérable,
(b) polluer le domaine pur `TradeRecord`, (c) rouvrir une faille de look-ahead.

**Décision.**
1. **`SqliteTradeJournal`** (SQLite stdlib, testable offline) — DB **dédiée** `data/journal.db`, JAMAIS
   mélangée aux `*.db` de prix (le journal n'est PAS régénérable : c'est de la donnée réelle). Interface
   **drop-in** de `TradeJournal` (append/all/pnls/to_csv) → interchangeable dans le moteur.
2. **`features_snapshot` en JSON TEXT** ; **UPSERT idempotent** sur `id` (retries/réimports sûrs) ;
   migration auto du schéma au 1er lancement (comme `bars_repo`).
3. **Flag `legacy` porté par la COUCHE STORAGE**, pas par `TradeRecord` : `append(trade, *, legacy=False)`
   + colonne `legacy` **indexée**. Le domaine reste pur ; la calibration filtre `WHERE legacy=0`. Les
   fills historiques (137, importés par `import_legacy_fills.py`) sont `legacy=1`, `features={}` —
   **jamais reconstruits a posteriori** (ce serait une fuite).
4. **`LiveTradingEngine` persiste par défaut** ; le backtest garde l'in-memory (paramétrable). Le dict de
   features transite **inchangé** de la décision (`Signal.features`) jusqu'au `TradeRecord`, jamais
   recalculé au fill — invariant vérifié par un **test contractuel de bout en bout**.

**Conséquences.**
- (+) Journal réel durable ; dès qu'un trade paper `legacy=0` arrive avec ses features, la calibration
  (MFE/MAE/expectancy/Kelly) redevient possible (N>0) — débloque le RDV 2026-08-06.
- (+) Séparation nette régénérable (prix) vs non-régénérable (journal) ; `TradeRecord` reste stdlib-pur.
- (+) Warning explicite si un trade live arrive sans features → détecte une régression de capture ML.
- (−) Cible prod ultérieure DuckDB/Postgres via la même interface (non fait, non bloquant).
- Corollaire hygiène (même session) : bug look-ahead trouvé dans `channel_break` (seuil polyfit sans
  tolérance → fausses cassures sur canal plat), corrigé `3c1c771`. La stratégie breakout **reste rejetée**.

## ADR-0025 — Données crypto LIVE : client-direct (pas de proxy serveur) + growth minimal
**Date :** 2026-06-29
**Contexte.** Demande d'un module crypto temps réel (graphe, jauge, analyse) et de boucles de
croissance (profils audités, parrainage débloquant de la compute). Or le site est **100 % statique**
(GitHub Pages) : **aucun backend**, donc **aucun proxy serveur** possible (`?url=…`), aucun compte,
aucune base de données serveur.
**Décision.**
1. **Live = client-direct** : WebSocket **navigateur** (Coinbase `ws-feed`, IP client → pas de
   géoblocage serveur) + REST **uniquement si CORS** (CoinGecko, alternative.me, DefiLlama, Bybit,
   OKX). Si une source bloque le CORS → **`n/d`**, jamais de chiffre inventé. Lib graphe en **UMD CDN
   lazy** (0 dépendance npm, v4 pinné). Refresh lent 60-90s, auto-refresh **visible-only**.
2. **Croissance : seule la boucle partage/embed** (URL encodée + X/Farcaster + iframe `?embed=1`
   read-only) est retenue. **Refusés** : profils de perf « audités/infalsifiables » et parrainage
   débloquant Dune/Glassnode/compute → exigent un backend (absent) **et** dégradent la marque
   institutionnelle (mécanique hype, contraire à « la discipline est le seul alpha »).
**Conséquences.** 0 €/statique préservé ; live réel mais best-effort (dégradation honnête) ; pas de
Kafka/ClickHouse/matching-engine (on *consomme* les plateformes, on n'est pas un exchange). Si un jour
un proxy est nécessaire → Cloudflare Worker gratuit (hors GitHub Pages), à rediscuter.

## ADR-0024 — Arrêt de la chasse à l'alpha directionnel → durcissement du risque
**Date :** 2026-06-25
**Statut :** accepté

**Contexte.** 4 hypothèses d'alpha directionnel (PEAD large, PEAD small/mid, clusters insiders,
funding crypto) ont été testées avec le pipeline honnête (event-study → placebo → coûts → DSR → PBO).
**Les 4 ont été rejetées.** Cas pédagogiques : un t-stat spectaculaire (insider t=8, funding t=-3,4)
désamorcé par le placebo (chevauchement de fenêtres + queues épaisses gonflent le t naïf). Confirme
DSR≈0 pour la 4ᵉ fois.

**Décision.**
- **On cesse de miner l'alpha directionnel dans la data gratuite** (rendements décroissants + risque
  de p-hacking croissant). Toute nouvelle hypothèse reste possible mais doit franchir le gate.
- **On industrialise l'edge prouvé** : gestion du risque. Overlay d'exposition (drawdown taper × vol
  prévue EWMA) câblé dans le preset, **défaut OFF** (opt-in `QUANT_RISK_OVERLAY=1`) car inerte sur un
  preset déjà peu drawdown — assurance tail, pas générateur de rendement.
- **Intégrité du reporting** : une source unique de vérité des métriques (`perf_summary`) ; aucun
  chiffre non reproductible dans le manifeste.
- **Survivorship** : correction partielle (seed curée + détection stale) ; résidu assumé (vintages
  point-in-time non gratuits) → backtests longs lus comme légèrement optimistes.

**Conséquences.**
- (+) Positionnement crédible : on ne vend pas un alpha inexistant ; la valeur (risque + beta) est
  prouvée ET reproductible. Audit contradictoire 3 rounds : 66 → 83/100.
- (+) Verdict **PRÊT POUR CAPITAL RÉEL LIMITÉ** sous conditions (sizing défensif + track record paper).
- (−) Pas de promesse de surperformance ; le produit est la qualité du processus, pas l'oracle.
- Négatifs documentés au ledger (`research/hypotheses.jsonl`) + manifeste → on ne re-teste pas en rond.

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

## ADR-0022 — Rendu DOM : tables en une chaîne complète + onglet isolé par try/catch
**Date :** session 15 (2026-06-16)
**Statut :** accepté
**Contexte.** L'aperçu interactif autonome (`build_interactive.py`) construisait les lignes
de tableau via un helper `div.innerHTML='<tr>…'`. Le **parseur HTML des navigateurs supprime
tout `<tr>/<td>` qui n'a pas de `<table>` ancêtre** : le helper renvoyait `null`/un nœud
incohérent, l'exception remontait et **stoppait tout le script après le Dashboard** → onglets
Portefeuille et Positions vides.
**Décision.**
- Chaque tableau est généré comme **une seule chaîne HTML complète**
  (`<table><thead>…</thead><tbody>…</tbody></table>`) puis injecté en **un seul** `innerHTML`.
- Les interactions (clic d'une ligne du screener) sont **câblées après injection** via
  `querySelectorAll` + attribut `data-i`, jamais par `onclick` sur des nœuds détachés.
- **Le rendu de chaque onglet est enveloppé dans un `try/catch`** : une erreur isolée ne peut
  plus vider les autres onglets (résilience d'affichage).
**Conséquence.** Les 3 onglets s'affichent indépendamment ; un futur bug de données dans un
onglet dégrade cet onglet seul, pas toute la page. Règle générale pour tout HTML généré :
ne jamais `innerHTML` un fragment de table orphelin.

## ADR-0023 — Stratégie best-practice : satellite risk-managed + cœur QQQ (DSR≈0)
**Date :** 2026-06-23
**Statut :** accepté
**Contexte.** Sprint « Alpha/Calmar » : améliorations #1-#6, #8, #10 (Ledoit-Wolf, porte de régime,
frein DD, anti cash-drag sans levier, tilt momentum, anti-fuite univers, breadth, gate DSR).
Mesure sur données RÉELLES (`make backtest-preset` / `calibrate-preset`) :
- Preset : CAGR 79.6 %, Sharpe 1.84, **Max DD −14.6 %** (Calmar ≈ 5.4 vs 0.17 au départ).
- Calibration : **Sharpe déflaté ≈ 0 sur les 27 combos** → AUCUN edge directionnel robuste.
- L'« alpha 6.9 % » d'avant était **gonflé par une fuite** (#2, désormais corrigée).
**Décision.** On n'invente pas d'alpha (López de Prado) :
1. Le preset est un **satellite à risque maîtrisé** — défaut `QUANT_DD_TARGET=0.25` (0.15 max-défensif,
   0.45 agressif). Son edge est la **gestion du risque** (DD bas, Sharpe élevé, décorrélé), pas le stock-picking.
2. Le **rendement absolu vient de la bêta honnête** : cœur indiciel `QUANT_CORE_SPEC="qqq:0.5"`.
   Pour plus de rendement → augmenter le QQQ (plus de bêta/DD assumés), PAS presser un alpha inexistant.
3. **#7 (Kelly) et #9 (vol-trigger) abandonnés** : DSR≈0 → ajouter des paramètres = surface d'overfitting,
   aucun gain attendu. Parcimonie.
**Conséquences.** Objectif réaliste = **Calmar/Sharpe élevés** (préservation du capital), pas battre le
QQQ en absolu sans sa bêta. Le gate #10 refuse toute combo non robuste → params défensifs par défaut.

## ADR-0026 — Ops-kit : certification, sub-agents, hooks, dashboard (rétro-doc de 627a0e2)
**Date :** 2026-07-02 (décision structurante du commit `627a0e2`, non documentée à l'origine — ADR créé au full-review).
**Contexte.** Après le verdict « PRÊT POUR CAPITAL RÉEL LIMITÉ », la priorité passe de la recherche d'alpha
à la **qualité opérationnelle**. CLAUDE.md référençait `vault/15_CERTIFICATION.md` comme gate de prod sans que
le protocole existe formellement.
**Décision.**
1. **Certification formelle** (`vault/15_CERTIFICATION.md`) : DRAFT→CANDIDATE→CERTIFIED→REVOKED, vérifié par `/full-review` / `/certify`.
2. **Sub-agents read-only** (`.claude/agents/`) : session-auditor, friction-clusterer, quant-critic, leakage-hunter, vault-architect, db-auditor — forkables pour l'analyse lourde.
3. **Hooks PostToolUse** (`.claude/hooks/`) : `file_guard` (<400 l/fichier, <50 l/fonction), `friction_log`.
4. **Dashboard ops** (`dashboard/claude_ops.py`) + **top1pct-pack** (modules quant durcis) + `config/risk_top1pct.yaml` + `config/macro_publication_lags.yaml`.
**Conséquences.** (+) Chaque composant de prod doit avoir une preuve citée. (−) `risk_top1pct.yaml` /
`macro_publication_lags.yaml` sont **orphelins** (aucun consommateur Python) ; 9/11 modules top1pct non câblés
→ dette suivie en P1 (`vault/14_FULL_REVIEW.md`).

## ADR-0027 — Full-review : invariant anti-fuite partagé + honnêteté « artefact » (2026-07-02)
**Date :** 2026-07-02.
**Contexte.** Le full-review a montré que le correctif anti-fuite `#2` (univers momentum prix-only) n'était
appliqué qu'à `preset_backtest()` ; il avait **ré-apparu** dans les 3 fonctions alimentant le dashboard
(`preset_equity_daily`/`preset_trade_log`/`preset_ledger`) → look-ahead + survivorship sur les chiffres AFFICHÉS
(`snapshot.py:2081`). Par ailleurs le top1pct-pack avait écrasé le Sizer enregistré `VolTarget` → suite rouge.
**Décision.**
1. **Invariant unique** : la sélection d'univers anti-fuite est extraite en **une** fonction partagée
   `_price_universe()` — plus jamais de logique de sélection dupliquée par fonction (source de la régression).
2. **Coûts obligatoires** : aucune courbe d'equity de prod n'est servie en **brut** (`preset_equity_daily` nette désormais le turnover).
3. **Honnêteté « artefact »** : tant qu'un chiffre affiché provient d'un chemin corrigé mais **non régénéré**,
   il est explicitement flaggé comme artefact dans `12_MANIFESTE_HONNETETE.md` (pas de claim « corrigé » prématuré).
4. **Régression = P0** : un composant de prod supprimé/cassé par un pack externe (ici le Sizer `vol_target`) est
   traité comme P0 (suite rouge = bloqueur), pas comme une simple dette.
**Conséquences.** (+) La fuite ne peut plus diverger entre backtest et dashboard. (−) Les chiffres affichés
(`Preset_Performance.md`) restent des artefacts jusqu'à un `make` de régénération sur le Mac (données réelles).
Voir `vault/14_FULL_REVIEW.md`.

## ADR-0032 — Ère paper = mono-broker Alpaca ; Bitmart = adaptateur futur-live gated (2026-07-03)
> *Renuméroté 0029→0032 le 2026-07-05 (collision : ADR-0029 = « long-only v1 », détectée par `vault_lint`).*
**Date :** 2026-07-03.
**Contexte.** La crypto était routée vers **Bitmart** (`routing.py`, `broker_symbol` en `/USDT`), un
courtier sans vrai mode paper (protégé seulement par `dry_run`). Objectif : accumuler des trades crypto
**paper réels** pour la calibration, sans exposer de capital. Alpaca offre un paper natif, le
fractionnement, l'idempotence `client_order_id` et la crypto spot en paires `/USD`.
**Décision.**
1. **Pendant l'ère paper, TOUTE la crypto passe par Alpaca paper.** `routing.route()` renvoie
   `broker=Alpaca`, `broker_symbol="{BASE}/USD"` pour les bases de la **whitelist** `ALPACA_CRYPTO_BASES`.
2. **TIF asset-class-aware** : `AlpacaBroker` envoie `TimeInForce.GTC` pour la crypto (24/7 ; `DAY` rejeté),
   `DAY` inchangé pour les actions.
3. **Bases hors whitelist Alpaca → EXCLUES de l'univers papier** (log explicite `snapshot.routing`),
   **jamais** routées vers Bitmart. Mieux vaut exclure une base supportée que router l'impossible.
4. **Bitmart reste un adaptateur *futur-live gated*** : code intact et testé, OFF par défaut (triple verrou,
   cf. `16_BROKER_ACTIVATION.md`). P0-SI-LIVE fermés (idempotence 1a, fills partiels 1b) ≠ autorisation
   d'activer — l'activation reste une décision explicite (garde-fou CLAUDE.md).
5. **Journal** : `LiveTradingEngine` enregistre désormais l'`asset_class` d'après le symbole (`/` → CRYPTO),
   plus d'`EQUITY` codé en dur → les trades crypto atterrissent correctement dans `journal.db` avec `features_snapshot`.
**Conséquences.** (+) Crypto paper réelle, journalisée, sans capital exposé ; un seul courtier à opérer.
(+) `vol_target` voit la vol réelle de l'instrument (ATR/prix, agnostique). (−) La whitelist Alpaca est
statique et conservatrice — à réconcilier au besoin avec `get_all_assets(asset_class=CRYPTO)`. (−) La vérif
d'un **vrai** fill crypto paper attend un run quotidien avec clés `ALPACA_*` (SELECT dans `journal.db`).
Voir `packages/execution/routing.py`, `alpaca_broker.py`, `live_engine.py`, `16_BROKER_ACTIVATION.md`.

## ADR-0030 — Dashboard : underwater dérivé client + downsampling LTTB partagé (2026-07-04)
**Date :** 2026-07-04. **Branche :** `feat/ui-analytics` (BLOC 5, isolée des brokers). PR #294.
**Contexte.** Le dashboard doit tracer l'equity (~2644 pts, 10 ans) **et** son drawdown underwater à 60 fps,
avec zoom et crosshair cohérents entre les deux. Deux options de plomberie : (a) nouveau champ API `drawdown`
servi par le backend ; (b) dériver l'underwater **côté client** depuis la série equity déjà servie.
**Décision.**
1. **Underwater dérivé client** (`lib/metrics.underwater` : `v/running_max − 1 ≤ 0`) — zéro nouveau champ API,
   la source de vérité reste l'equity unique (pas de risque de désync backend↔front).
2. **Downsampling LTTB partagé** (`lib/metrics.lttb`, ~600 pts) recalculé à chaque fenêtre de zoom, sur equity
   ET underwater → forme (pics/creux) préservée, 60 fps. **Invariant :** LTTB échantillonne sur le champ `.v` ;
   downsampler **sur `underwater()` (qui porte `.v`), jamais après renommage** — sinon aires `NaN`, LTTB dégénère
   en « 1er point par bucket » et le **pire DD est sous-estimé** (bug trouvé et corrigé cette session).
3. **Fenêtre de zoom unique** (`win` levée dans `PerformancePanel`) pilote les deux graphes + `syncId` recharts
   commun → axes X synchronisés et crosshair partagé. `EquityChart`/`DrawdownChart` `memo`ïsés.
4. **Sémantique couleur stricte** (rappel ADR design) : `--pos`/`--neg` = P&L plein UNIQUEMENT ; régime =
   tokens **outline** désaturés (`cyclePalette`, `badge-regime`). Aucun hex en dur dans les composants.
**Conséquences.** (+) Un seul contrat de données (equity) ; underwater toujours cohérent avec la KPI Max DD
(validé : « pire » affiché = −25,4 % = `metrics.max_drawdown`). (+) Pas de charge backend supplémentaire.
(−) Le calcul underwater + LTTB est refait à chaque render/zoom côté client (borné par `useMemo`, négligeable à 2644 pts).
Voir `apps/web/components/{PerformancePanel,EquityChart,DrawdownChart}.tsx`, `apps/web/lib/metrics.ts`.

## ADR-0031 — LiveTradingEngine RÉTROGRADÉ en moteur de simulation ; run_live.py = chemin de prod unique (2026-07-05)
**Contexte.** Depuis P0-4 (Phase 1 : journal direct à la décision, Phase 2 : round-trip des ventes),
le chemin de production réel est `scripts/run_live.py` (cron launchd 16h05) : réconciliation
cible↔broker, journal `data/journal.db` (`legacy=0`, features figées à la DÉCISION), fermeture FIFO
des lots. `LiveTradingEngine` (`packages/execution/live_engine.py`) n'est plus appelé par aucun
chemin de prod — uniquement `scripts/demo_paper_loop.py` et les tests. Laisser deux « moteurs live »
créait un risque de divergence (lequel journalise ? lequel porte les garde-fous ?).
**Décision.** **Rétrograder** (pas supprimer) : docstring de statut explicite (« PAS le chemin de
production »), classe et exports conservés (aucun churn de tests/démos). Il reste le banc d'essai
de la logique stop/target/kill-switch barre-par-barre — de la valeur de test, zéro ambiguïté de prod.
**Alternatives rejetées.** (a) Supprimer : perd le banc de simulation et casse démos/tests pour un
gain nul ; (b) Unifier run_live sur LiveEngine : refonte risquée près du RDV paper (déjà rejetée
le 2026-07-04, décision (b) journal direct).
**Conséquences.** (+) UN chemin de prod, journalisé et alerté ; (+) évolution prod = `run_live.py`
uniquement ; (−) parité stop/target entre simulateur et prod à re-vérifier si on ajoute des stops
au chemin réel (aujourd'hui le preset n'en émet pas — réconciliation par poids).


## ADR-0033 — Runner paper CLOUD (GitHub Actions) en 2e canal d'exécution, journal persisté sur HF privé (2026-07-05)
**Contexte.** Le rebalancement paper dépendait du Mac allumé (launchd 16h05). Besoin utilisateur :
tourner Mac éteint, à 0 €. Contrainte : le journal `data/journal.db` (features de décision +
round-trips, P0-4) doit SURVIVRE entre des runners CI éphémères, sans exposer son contenu
(repo public, positions = confidentiel).
**Décision.** `.github/workflows/paper.yml` (lun-ven 14h35 UTC, marché US ouvert été/hiver) exécute
le MÊME chemin de prod (`run_live.py --live --yes`) avec les clés Alpaca **paper** en secrets
chiffrés ; `scripts/hf_journal.py` pull/push le journal vers un dataset Hugging Face **PRIVÉ**
(refus de push si le dataset est public). Gate propre si secrets absents.
**Sûreté du double-run.** Mac + cloud le même jour = sans danger : la réconciliation est par
DELTA sur les positions broker (source de vérité) → le 2e passage voit ~0 et n'envoie rien.
MAIS chaque runner ne journalise que SES ordres → les deux journaux divergent. Règle : choisir
UN runner principal (recommandé : cloud) ; le Mac consulte via `make journal-pull`.
**Frontière définitive.** Cloud public = paper POUR TOUJOURS. Le trading réel (post-RDV
2026-08-06, si GO) restera local-only (clés dans `.env` Mac, jamais en CI publique) — surface
supply-chain (pip + actions tierces) inacceptable pour des clés réelles.

## ADR-0034 — Anonymat du dépôt public : statu quo assumé (option b) (2026-07-05)
**Contexte.** L'audit GitHub du 2026-07-05 a montré : vitrine sous le pseudonyme `7noctis7`
(canonique, l'ancienne URL redirige) mais des commits historiques portent un nom d'auteur
relié à l'identité réelle → le lien pseudonyme↔identité est trouvable par archéologie git.
Options : (a) assumer publiquement l'identité ; (b) statu quo ; (c) réécrire l'historique des
auteurs (`git filter-repo` + force-push destructif).
**Décision (utilisateur, 2026-07-05) : (b) statu quo.** Le lien reste techniquement trouvable
mais non affiché. Pas de réécriture d'historique (destructif, casse les clones, bénéfice
limité : toute copie antérieure conserve l'info). Conséquence assumée : le projet ne doit
JAMAIS contenir de donnée dont la sensibilité dépendrait de l'anonymat (déjà le cas :
positions réelles local-only, zéro secret tracké — vérifié par audit + gitleaks CI).
Si la posture change un jour → nouvel ADR (option a : simple ; option c : opération dédiée).
