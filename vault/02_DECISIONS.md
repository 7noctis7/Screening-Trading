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

## ADR-0035 — DSR : le seuil de déflation était inatteignable par artefact d'unités (2026-08-20)
**Date :** 2026-08-20.
**Contexte.** Le gate exige `DSR > 0,5`. Le seuil `sr_star` est construit à partir de `sr_std`,
la dispersion des Sharpe entre essais, lue au ledger par `deflation_params`. Or les scripts
enregistrent au ledger un Sharpe **ANNUALISÉ** (`_stats` multiplie par √per_year), tandis que les
appelants du DSR (`breakout.py`, puis `alpha_lab.py`) passent un Sharpe **PAR PÉRIODE** — ce que
la docstring de `deflated_sharpe_ratio` exige explicitement (« MÊME périodicité »).

**Mesure du défaut (2026-08-20, ledger réel de 18 essais / 15 facteurs distincts).**
`sr_std = 0,972` (dispersion des Sharpe annualisés stockés : 0,20 · 1,90 · 2,10 · 2,44 · 2,66)
⇒ `sr_star = 1,721` **par barre** ⇒ il fallait un Sharpe **annualisé de 27** en quotidien
(ou 6,0 en mensuel) pour franchir le gate. **Aucun candidat ne pouvait passer.** Les rejets
successifs n'étaient donc pas, pour cette composante, des verdicts de marché mais un artefact.

Le défaut était **latent** : il ne s'active que lorsque le ledger contient ≥ 2 Sharpe. Le
correctif de juillet (repli `sr_std = √(1/n)` au lieu de 1,0) avait réparé le CHEMIN DE REPLI ;
il n'avait pas vu que le chemin nominal, lui, mélangeait deux unités.

**Décision.**
1. `deflation_params` n'admet dans `sr_std` que les enregistrements dont la **périodicité est
   connue** : `sharpe_period` explicite, ou `sharpe` accompagné de `periods_per_year`. Les
   autres sont **exclus — jamais devinés** (deviner 252 pour un essai mensuel diviserait le
   seuil par 4,6 sans le dire).
2. Moins de deux essais utilisables ⇒ `None` ⇒ repli sur `√(1/n)`, l'H0 de Bailey-López de Prado,
   qui est falsifiable.
3. Les scripts (`preset_lab`, `alpha_lab`) enregistrent désormais `periods_per_year` et, quand
   c'est naturel, `sharpe_period`. Le ledger redeviendra progressivement exploitable.
4. `deflation_diagnostic()` rend la déflation **auditable** : combien d'essais comptent, combien
   sont exclus, et si l'on est en repli.

**Conséquence assumée — le gate devient MOINS sévère, et c'est voulu.** Avec le repli Bailey et
15 essais, le seuil passe à un Sharpe annualisé d'environ **0,65 sur ~7 ans mensuels**. Un
Sharpe annualisé de 1,5 donne désormais DSR ≈ 0,98 ; il donnait ≈ 0,00 la veille. Ce n'est pas
un assouplissement de confort : c'est le retour à un seuil qui a un sens statistique. Un Sharpe
de 0,30 reste rejeté (test de non-régression).

**À faire.** Re-runner les hypothèses historiquement rejetées : leurs verdicts DSR sont invalides
sur cette composante. Un rejet reste un rejet s'il tenait par le placebo, le PBO ou le sabotage —
mais il doit être re-établi, pas supposé.

## ADR-0036 — Périmètres de risque : RiskEngine (streaming), order_gate (rebalancing) (2026-08-25)
**Contexte.** Deux barrières de risque coexistaient sans frontière claire :
- `RiskEngine` : moteur événementiel de streaming, stops/récompense-risque par signal.
- `order_gate` : limite de position, utilisée UNIQUEMENT en production (`run_live.py`).

Risque : un développeur aurait pu brancher `RiskEngine` dans le rebalancing sans voir le
problème : interface mismatch fatal (RiskEngine attend signal/barre/stop par ordre ; rebalancing
reçoit une cible de portefeuille).

**Décision.**
1. **Périmètre explicite dans le module** `packages/risk/engine.py` : docstring (~50 lignes)
   formalisent que `RiskEngine` est RÉSERVÉ au streaming, `order_gate` au rebalancing.
2. **4 tests architecturaux** (`tests/risk/test_perimetres.py`) pinning la limite :
   - Le rebalancing utilise `order_gate`, jamais `RiskEngine`.
   - `RiskEngine` n'est appelé que du moteur streaming.
   - Rationale : événementiel vs stationnaire (cible).
   - Chaque test porte le message : « Ce test doit être supprimé ET l'ADR mis à jour avant
     de violer cette limite. »
3. **Pas de nouvelle couche** : les 2 barriers restent indépendantes, l'absence de `RiskEngine`
   en rebalancing est DESIGNED, pas oversight.

**Conséquence.** (+) Violation accidentelle est impossible (test rouge + ADR à réécrire). (+) La
raison est documentée (contexte = moteur événementiel vs batch). (−) Deux chemins de risque
coexistent (mais ils opèrent en série, pas en parallèle : rebalancing → order_gate → broker).

**Déploiement.** PR #343, commit `caed949`.

## ADR-0037 — Grille d'alignement sans NaN : intersection de calendriers vs union (2026-08-25)
**Contexte.** Date-alignment #341 a révélé que les trois fonctions de reporting (equity_curve,
trade_log, ledger) utilisaient une **fenêtre par rang** (union de dates, remplie par NaN).

Problème critique : le ledger (parts/cash/PnL) n'a pas de garde-fou NaN → une valeur nulle
devient silencieusement une plausible valeur de P&L, FALSE POSITIVE incomparablement plus grave
qu'une vraie exception (donne du bruit « joli »).

Comparaison empirique (data réelle) : ancien code (NaN) = Sharpe 0,92 ; nouveau (intersection
sans NaN) = Sharpe 1,34. ~12 des top-30 positions étaient choisies par artefact de calendrier
(stock 5j/semaine, crypto 7j/semaine, 11 ans = 3 ans de drift).

**Décision.**
1. **`aligner_sans_trous(data, syms, min_noms)`** : retourne intersection des calendriers (rank-
   based subset par couverture, décroissante). **Garantie : zéro NaN** aux trois sorties.
2. **Trade-off accepté** : la fenêtre est plus COURTE (plus long = plus de trous = moins de noms)
   mais **bulletproof** (aucun NaN ne s'échappe pour devenir faux P&L).
3. Les trois presets (`preset_equity_daily`, `preset_trade_log`, `preset_ledger`) l'utilisent
   depuis #341, chaînées avec le backtest `aligner_par_date` → grille homogène partout.
4. **Vieux code supprimé** : `fenetre_par_rang` (117 lignes, zero call sites restants).
5. Tests migrants : 7 vieux tests → nouveaux tests mêmes intents (`test_aligner_sans_trous_*`).

**Conséquence.** (+) Ledger **totalement cohérent** avec les courbes d'equity affichées. (+)
Baseline performance réelle mesurable (DSR, max DD) sans leurre de NaN. (+) Calendrier stock vs
crypto enfin séparé proprement (intersection = respecte les deux univers). (−) Fenêtre moyenne
plus courte (~6 ans au lieu de 11 ans, dépend du top-N) — acceptable car mieux vaut 6 ans VRAIS
que 11 ans FAUX.

**Déploiement.** PR #341, commits `fb4d380` + refactoring dans `fb4d380`.

## ADR-0038 — `preset_backtest.py` devient une façade : découpage en sept modules (2026-08-25)

**Contexte.** Le fichier avait atteint **793 lignes avec cinq fonctions au-dessus de 50**, contre
la règle d'architecture 400/50. La conséquence n'était pas esthétique : le hook `file_guard`
refuse toute édition d'un fichier hors règle, donc **le rolling universe, le câblage d'`impact.py`
et les séries macro étaient tous bloqués derrière ce mur unique**. Trois tentatives d'ajout de
fonctionnalité ont été rejetées par le hook avant que le mur soit traité pour lui-même.

**Décision.** Découpage par responsabilité, `preset_backtest.py` devenant la **façade** :

| module | responsabilité |
|---|---|
| `preset_config.py` | constantes de gating + `momentum_rank` + `_price_universe` |
| `preset_core.py` | panel, univers, garde-fous (classe `Compteurs`), poids et gross du pas |
| `preset_weights.py` | poids de production, `_weights_at`, `_concentrate` |
| `preset_curves.py` | equity quotidienne, journal de trades |
| `preset_livre.py` | livre de comptes parts/cash (achat/vente, PRU, frais) |
| `preset_compta.py` | ledger : déroulé, FIFO latent, réconciliation |
| `preset_backtest.py` | façade (`__all__`) + boucle du backtest |

1. **API publique inchangée.** Les onze noms importés par `apps/api/snapshot.py`, les scripts et
   les tests restent importables depuis `preset_backtest`. Protégé par `__all__` **et** par
   `tests/backtest/test_preset_architecture.py`, qui échoue si un nom disparaît.
2. **Équivalence bit-à-bit exigée, et vérifiée.** Les tests verts ne démontrent PAS l'absence de
   changement de comportement — ils couvrent ce qu'ils couvrent. Comparaison directe de
   l'ancienne implémentation contre la nouvelle sur **10 configurations** (défaut,
   overlay+cap+denoise, univers legacy, sans alignement, gates off, les cinq fonctions publiques,
   ledger avec cœur indiciel), comparaison récursive **sans tolérance**. Sorties identiques.
3. **Deux déduplications.** `preset_equity_daily` ré-implémentait mot pour mot `_weights_at` ;
   le classement momentum était écrit deux fois (backtest + `_price_universe`). Une seule source.
4. **L'ordre des écritures du ledger est préservé** (cœur avant satellite à chaque rééquilibrage) :
   l'attribution du P&L latent se fait en FIFO sur la liste `trades`, donc l'ordre est du
   comportement, pas de la mise en forme.

**Conséquence.** (+) Les trois chantiers bloqués deviennent éditables. (+) Le ledger, jusqu'ici la
partie la plus dense (207 lignes d'affilée), est isolé derrière un objet `Livre` testable seul.
(+) ruff : 240 erreurs sur l'ancien fichier → 164 sur les sept nouveaux. (−) Sept fichiers à
parcourir au lieu d'un : la façade et ce tableau sont là pour ça. (−) Un import de plus en
profondeur pour qui voudrait un interne (`preset_core.univers_backtest`, par exemple) — assumé,
c'est la contrepartie d'une frontière publique explicite.

**Non fait, et pourquoi.** Ce découpage **ne change pas l'alpha** : Sharpe 1,35 inchangé, par
construction (équivalence bit-à-bit). Il ne prétend pas être une amélioration de performance,
seulement la levée du blocage qui empêchait d'en tenter une.

**Déploiement.** Commit `4984ecb`.

## ADR-0039 — Tout verdict du labo porte son incertitude (2026-08-26)

**Contexte.** Le gate du labo compare des estimations **ponctuelles** de Sharpe à un seuil fixe
(+0,05) et conclut « promu » ou « rejeté ». Le run du 25/08 a produit neuf « rejeté » avec des
ΔSharpe de −0,01 à −0,12, lus comme neuf verdicts distincts. Aucun ne portait d'erreur-type, donc
rien ne disait s'ils étaient distinguables de zéro — ni les uns des autres.

**Ce que la mesure a révélé.** Test de Jobson-Korkie (1981) avec correction de Memmel (2003), sur
Sharpe **appariés**. L'appariement est le point technique : deux variantes tournent sur les mêmes
dates avec des positions largement communes (ρ > 0,95) ; les traiter comme indépendantes
surestimerait massivement l'incertitude et rendrait tout indiscernable. Puissance sur 126 pas :

| ΔSharpe vrai | détecté |
|---|---|
| +0,05 (**seuil du gate**) | **7,3 %** |
| +0,15 | 30,2 % |
| +0,32 | 85,1 % |
| +0,60 | 100 % |

**Le seuil de promotion est trois fois sous le plancher de détection** (~+0,14 à ρ = 0,99). À
+0,05, le taux de détection dépasse à peine le taux de faux positifs (5 %) : la décision est un
tirage au sort déguisé en verdict.

**Décision.**
1. Chaque verdict porte une ligne d'incertitude : ΔSharpe ± SE, IC95, ρ, p, et un verdict à trois
   états — `meilleur` / `pire` / **`indiscernable`**. « Indiscernable » n'est PAS « équivalent » :
   c'est « cet échantillon ne permet pas de trancher ».
2. Un bloc **PUISSANCE** s'affiche **avant** les verdicts. On lit ce que l'échantillon peut voir
   avant de lire ce qu'il prétend montrer.
3. **Le seuil de +0,05 n'est PAS relevé.** Le relever à +0,15 rendrait le gate cohérent avec sa
   puissance, mais fermerait la porte à tout levier réel de taille modeste. Le bon correctif est
   d'allonger la fenêtre, pas de durcir un seuil sur un échantillon trop court. On documente
   l'écart plutôt que de le maquiller ; `test_le_gate_a_005_est_sous_le_plancher_de_detection`
   casse le jour où la fenêtre s'allonge assez pour rouvrir la question.
4. **Calibration vérifiée dans la suite de tests**, pas dans un script jetable. Monte-Carlo sous
   H0 : 4,95 %–5,33 % de rejets à ρ = 0,99 / 0,95 / 0,80 / 0,00. Un test non calibré est pire
   qu'aucun test — il donne une autorité chiffrée à une décision arbitraire.

**Conséquence sur l'arbitrage `k médian = 1`.** Le diagnostic de covariance recommande
l'inverse-vol ; la mesure rejette le débruitage RMT (ΔSharpe −0,07). Avec l'erreur-type, la
contradiction se dissout : **−0,07 est indiscernable de zéro**. Ni le diagnostic ni la mesure ne
justifient de changer le défaut. Point fermé, sans changement de comportement.

**Ce que cet ADR ne fait pas.** Il ne corrige PAS la multiplicité des essais — c'est le rôle du
DSR et du ledger (N = 25). Il suppose des rendements i.i.d. : l'autocorrélation gonfle le Sharpe
et resserre à tort l'intervalle. Et il **n'améliore aucun chiffre** : Sharpe 1,35 inchangé. Il
change ce qu'on a le droit de conclure, pas ce que la stratégie produit.

**Déploiement.** Commit `9e475d3`.

## ADR-0040 — Un ordre qui ne peut pas se remplir est REPORTÉ, jamais envoyé (2026-08-26)

**Contexte.** Le compte paper contenait le cœur QQQ, huit lignes crypto et **zéro action du
satellite**, avec 28 % de cash exactement à la place manquante. `alpaca_broker` envoie les
actions en `TimeInForce.DAY` sans `extended_hours` et la crypto en `GTC` (24/7) : hors séance,
seule la crypto peut se remplir. Aucun contrôle d'horaires n'existait dans le chemin
d'exécution — vérifié par recherche exhaustive.

**Ce qui a rendu le défaut durable.** Pas le défaut lui-même, mais le SILENCE autour : l'erreur
de courtier était tronquée à 40 caractères, et le statut de l'ordre n'était jamais relu après
envoi. Un satellite vide pendant des semaines ne produisait aucune ligne de journal.

**Décision.**
1. **`packages/execution/market_calendar.py`** — périmètre volontairement étroit : répondre
   « peut-on envoyer cet ordre maintenant ? », rien de plus. Pas de demi-séances, pas
   d'enchères, pas de `session_minutes` : ce n'est PAS le F11 complet, et le prétendre serait
   pire que l'absence. stdlib pure, sans réseau — un garde-fou d'exécution ne doit pas
   dépendre d'un appel qui peut échouer.
2. **Fériés en table EXPLICITE**, pas calculés : une règle de calcul fausse est silencieuse,
   une date manquante est visible. `feries_a_jour()` + un test qui casse à la péremption.
3. **Reporter, pas bloquer, et le DIRE** : compte, montant total, et le conseil de décaler le
   cron. Un ordre reporté n'est pas une erreur ; un ordre reporté en silence en est une.
4. **Les liquidations sont reportées aussi.** Contrairement au portail de risque — où un
   désengagement passe toujours, parce que le bloquer augmenterait le risque — il ne s'agit
   pas ici d'une décision de risque mais de physique : hors séance, une vente ne se remplit
   pas davantage qu'un achat.
5. **Échappatoire explicite** `QUANT_IGNORE_SESSION=1`, jamais le défaut.
6. **Erreur de courtier complète** à l'écran (200 car.) et dans le journal structuré.

**Conséquence.** (+) Le cas observé devient impossible à rater. (+) Deux tests du portail de
risque ont viré au rouge sous le nouveau garde-fou — leur rôle exact ; isolés par une fixture
explicite. (−) Un run hors séance ne fait plus rien côté actions : c'est le comportement voulu,
mais il faut décaler le cron pour que le rebalancement ait lieu (séance = 15:30-22:00 CEST).

**Ce que cet ADR ne fait PAS.** Le statut de l'ordre n'est toujours pas relu après envoi : un
ordre accepté puis rejeté reste compté comme réussi. Trou connu, laissé ouvert et inscrit au
TODO plutôt que masqué.

**Déploiement.** Voir aussi ADR-0041 (alignement du panel de production).

## ADR-0041 — Le panel de PRODUCTION s'aligne comme le backtest (2026-08-26)

**Contexte.** `preset_latest_weights`, la fonction qui pilote `make live`, empilait les séries
POSITIONNELLEMENT (`fenetre_commune`) alors que le backtest était passé à l'alignement par date
en #341. **Production et backtest ne mesuraient donc pas la même chose** — le backtest qui
valide la stratégie ne validait pas ce que la production exécute.

Sur un panier mêlant actions (5 séances/semaine) et crypto (7 j/7), les colonnes des deux
familles portaient des dates différentes. La covariance de l'ERC, l'indice de marché de la
porte de régime et le tilt momentum étaient tous calculés sur ce mélange.

**Décision.** Migration sur **`aligner_sans_trous`** — aligné par date ET garanti sans NaN.
Pas `aligner_par_date` : la production dimensionne des ordres réels, un NaN y produirait un
poids FAUX plutôt qu'une erreur visible. Même arbitrage que pour le ledger (ADR-0037).

**Mesure.** Deux familles aux économies STRICTEMENT identiques (même dérive et même volatilité
annuelles), ne différant que par leur calendrier : toute préférence est un artefact par
construction. Rapport de poids par ligne crypto/action, neutre = 1,00 :

| | médiane | étendue |
|---|---|---|
| avant | 0,88 | [0,63 ; 1,31] |
| après | **0,97** | [0,77 ; 1,16] |

**Honnêteté sur la portée.** Ce biais est RÉEL mais **n'explique pas** le satellite vide —
l'effet est trop faible et sans direction nette. Il a été trouvé en cherchant autre chose, et
corrigé pour lui-même. Deux verrous : le test statistique ci-dessus, et un test structurel qui
inspecte les IMPORTS effectifs du module (pas son texte — le nom de l'ancienne fonction reste
cité dans la docstring qui explique la migration).

**Déploiement.** 1330 tests verts.

## ADR-0042 — Un ordre a QUATRE issues, pas deux (2026-08-26)

**Contexte.** `run_live` incrémentait `sent` dès que l'appel courtier ne levait pas
d'exception, sans lire la réponse. Alpaca accepte un ordre puis peut le rejeter : le
récapitulatif annonçait des ordres partis alors que rien n'était passé. C'est le trou resté
ouvert à la fin d'ADR-0040.

**Décision.** `packages/execution/order_outcome.py`, duck-typé et sans dépendance :

| issue | sens |
|---|---|
| `REJETE` | le courtier refuse — ne se remplira JAMAIS. L'angle mort. |
| `REMPLI` | exécution confirmée (totale ou partielle) |
| `EN_COURS` | accepté, remplissage non confirmé — **cas normal** à la soumission |
| `INCONNU` | réponse inexploitable : ni succès ni échec, et surtout pas un succès |

La distinction `REJETE` / `EN_COURS` est tout l'intérêt : sans elle, on choisit entre ignorer
les rejets (l'ancien comportement) et crier au loup à chaque ordre normal. Un rejet ne compte
plus comme envoyé et n'est plus journalisé comme une ouverture.

**Deux régressions évitées de justesse, et c'est le point méthodologique.** Le module a été
confronté aux QUATRE courtiers du dépôt avant activation : Bitmart et Binance renvoient
`OrderStatus.SUBMITTED` (vocabulaire interne, absent du vocabulaire Alpaca) et
`AlpacaBroker.close_position` renvoie un **booléen**, pas un ordre. Sans ces deux cas, le
correctif aurait cessé de compter tous les ordres crypto et toutes les liquidations — soit
le défaut inverse de celui qu'il corrige.

**Une docstring démentie par son test.** `classer()` affirmait « ne lève JAMAIS » ; un objet
exposant `status` en propriété qui lève traversait. La garantie est désormais tenue par un
`try`, pas par la prudence supposée du code appelant.

**Conséquence.** (+) Un rejet devient visible et chiffré. (−) Le compteur d'ordres envoyés
baissera : c'est le but, il était faux.

## ADR-0043 — L'écran ne promet pas ce que l'exécuteur refusera (2026-08-26)

**Contexte.** `/positions` badgeait « à acheter » toute cible du modèle non détenue, sans
jamais consulter le plancher de ligne que `decider()` applique. Une cible sous le plancher
n'est jamais ouverte — l'écran affirmait donc une action qui n'aurait pas lieu. C'est la
question de l'utilisateur qui a révélé le défaut : « pourquoi ça me dit d'acheter mais ça ne
rebalance pas ? »

**Décision.**
1. Badge **« bloqué · sous le plancher »** avec le montant qui manque, au lieu de
   « à acheter ».
2. **Bandeau** quand AUCUNE cible ne peut partir — le cas qui rend la liste trompeuse :
   elle ressemble à des achats imminents alors qu'aucun ordre ne partira. Le bandeau nomme
   les deux leviers (capital de la poche, `QUANT_MIN_POSITION`) et rappelle qu'une exposition
   brute réduite par la porte de régime fait aussi passer des lignes sous le plancher.
3. Le plancher vient de l'API (`min_position`), **jamais recodé côté front** : deux sources
   pour une même règle garantissent la dérive.

**Conséquence.** (+) Une famille entière de confusion disparaît : l'écran et l'exécuteur disent
la même chose. (−) Sur un petit capital, la page affichera surtout des lignes bloquées — c'est
l'information juste, pas un régression d'affichage.

## ADR-0044 — Le preset dit POURQUOI il ne demande rien (2026-08-26)

**Contexte, et il est inconfortable.** Un compte paper sans aucune action du satellite a résisté
à **trois hypothèses successives** — plancher de ligne, horaires de marché, mode léger — toutes
formulées à partir du code, toutes réfutées par la mesure. Trois allers-retours avec
l'utilisateur pour un diagnostic qu'une ligne de journal aurait donné immédiatement.

La cause de cette errance n'est aucune des trois : c'est que `preset_latest_weights` renvoie
`{}` pour **au moins six raisons** sans en distinguer aucune.

| étage | cause d'un résultat vide |
|---|---|
| éligibilité | moins de 5 titres avec ≥ 200 barres |
| score qualité | **repli silencieux** sur `syms[:top_k]`, ordre ARBITRAIRE |
| panel | intersection des dates < 200, ou < 2 noms |
| covariance | fenêtre < 20 barres |
| exposition | une porte (DD-target / régime / ampleur) à zéro |
| concentration | aucun poids au-dessus du seuil |

**Décision.** `packages/backtest/preset_diag.py` : un journal d'étages, purement observationnel.

1. `preset_latest_weights_explique` renvoie `(poids, Diag)` ; `preset_latest_weights` délègue et
   ne renvoie que les poids. **Aucun chiffre ne change** — vérifié sur 5 tirages.
2. **Chaque porte publie son multiplicateur.** C'est l'information qui manquait le plus : une
   exposition nulle est légitime (« risk off, tout en cash ») mais doit être AFFICHÉE.
3. **Le premier étage bloquant gagne** : la cause racine, pas le dernier message écrit.
4. **Le repli sans score qualité est tracé comme un incident.** `len(q) >= 5` basculait sur un
   univers dans l'ordre du dictionnaire sans un mot — le repli le plus dangereux de la chaîne,
   parce qu'il produit un résultat plausible et faux plutôt qu'une erreur.
5. Publié dans le snapshot (`preset_diagnostic`), affiché par `run_live` **seulement quand le
   satellite actions est vide** — un diagnostic permanent deviendrait du bruit.

**Ce que cet ADR ne fait PAS.** Il ne dit toujours pas pourquoi CE compte a un satellite vide :
il donne le moyen de le savoir au prochain run. C'est délibéré — une quatrième hypothèse aurait
eu la même valeur que les trois premières.

**Leçon transversale de la journée.** Quatre défauts corrigés (taux inventé, benchmark en NaN,
ordres hors séance, ordres rejetés comptés comme envoyés) partagent une seule racine : **un
chemin qui échoue sans le dire**. Le silence a coûté plus cher que chacun des défauts.

## ADR-0045 — Le repli d'univers est PRINCIPIEL, jamais l'ordre du dictionnaire (2026-08-26)

**Contexte, établi par la mesure et non par déduction.** Le diagnostic livré en ADR-0044 a donné
le fait sur données réelles :

```
score qualité      ⚠️  0 titre(s) scoré(s) → REPLI sur les 12 premiers, ordre ARBITRAIRE
exposition brute   DD-target 0.255 × régime 0.000 × ampleur 0.000  =  0.0000
⛔ ARRÊT : exposition brute NULLE — porte(s) à zéro : régime, ampleur
```

**La chaîne causale.** `make live` tourne en mode LÉGER, qui coupe la section `fundamentals` :
`quality` est donc **toujours vide à l'exécution**. Le repli `syms[:top_k]` prenait alors les
12 premiers symboles du dictionnaire. Or `mkt = A.mean(axis=0)` — l'indice de marché que lisent
les portes de régime et d'ampleur — est la moyenne de l'univers RETENU. Les portes mesuraient
donc un panier tiré au hasard, concluaient « chute > 15 %, aucun titre au-dessus de sa MM200 »,
et annulaient l'exposition.

**Le satellite actions n'était pas vide par décision de risque. Il était vide parce qu'on
mesurait le risque d'un panier arbitraire.** Toutes les exécutions de production passaient par
ce chemin.

**Décision.** Le repli utilise `_price_universe` : le même classement momentum que le backtest,
aligné par date, prix seuls. Il ne dépend d'aucune source externe, donc il fonctionne quelle que
soit la raison de l'absence de scores — mode léger, réseau coupé, quota d'API épuisé. Un repli
doit être un choix dégradé mais SENSÉ, jamais un accident d'ordre d'itération.

**Vérification.** Panier construit pour piéger l'ancien comportement : les 12 premiers du
dictionnaire sont les PIRES titres, les meilleurs sont en fin. Ancien repli → les 12 pires
retenus, portes à 0,00, exposition nulle. Nouveau repli → les 12 meilleurs retenus, exposition
1,00. Deux tests, rouges sans le correctif.

**Ce que cet ADR ne tranche PAS.** Faut-il retirer `fundamentals` de `_LITE_SKIP` ? Le repli
momentum rend la production correcte sans cela, mais l'univers reste alors sélectionné par
momentum et non par qualité — ce n'est pas ce que le design prévoyait. Arbitrage entre justesse
du signal et durée du snapshot, laissé explicite au TODO plutôt que résolu par effet de bord.

**Leçon de méthode, la plus coûteuse de la journée.** L'hypothèse « le mode léger coupe
`fundamentals` » était JUSTE et a été écartée à tort : la mesure censée la tester lisait
`snap["preset_allocation"]` à la racine, où la clé n'existe pas (elle est sous `dashboard`).
Une bonne piste abandonnée sur la foi d'une mesure non validée. **Valider l'instrument avant de
lui faire réfuter une hypothèse.**

## ADR-0046 — Le point de mesure du momentum n'est PAS le même en backtest et en production (2026-08-27)

**Contexte.** `_price_universe` classe l'univers par momentum au DÉBUT de la fenêtre commune
(`s0 = max(lookback, 50)`). C'est l'anti-fuite #2 : en backtest, classer au dernier point
reviendrait à choisir l'univers en connaissant l'avenir. La fonction est partagée avec le
chemin de PRODUCTION depuis ADR-0045, où ce même point produit un résultat absurde — sur
2762 barres, `s0 = 120` sélectionne sur le momentum de début 2015, puis fige. Constaté :
l'indice du panier périmé tombait sous −15 %, la porte de régime annulait l'exposition,
pendant que la porte d'ampleur voyait 100 % du même univers au-dessus de sa MM200.

**Décision.** Un paramètre explicite `au_dernier_point`, défaut `False`. Le backtest garde
le point de départ ; seule la production le passe à `True`. En production, « aujourd'hui »
EST le dernier point connu : il n'y a aucune information future à fuiter. Deux tests
verrouillent l'asymétrie dans les deux sens — un défaut sur le chemin backtest serait une
fuite, un défaut sur le chemin production un univers périmé.

**Conséquences.** L'univers de production suit le marché au lieu d'être figé. Le garde
d'indice de `momentum_rank` passe de `> s0` à `>= s0` : on lit `s0 - 1`, donc une série de
longueur `s0` est lisible, et le garde strict aurait vidé la sélection au dernier point pour
la faire retomber sur l'ordre du dictionnaire — le défaut même que ADR-0045 ferme. Sans effet
sur le backtest, où `s0 = 120` et les séries font 2762 barres.

**Corollaire de méthode.** Un repli qui se dégrade en silence doit être testé sur un jeu où
TOUS les ordres arbitraires (insertion, alphabétique) donnent la mauvaise réponse. Une
première version de ces tests était verte parce que le tri alphabétique d'`aligner_par_date`
faisait accidentellement tomber juste le repli arbitraire.

## ADR-0047 — Une porte qui bloque doit publier ses CHIFFRES, pas seulement son multiplicateur (2026-08-27)

**Contexte.** `régime = 0.000` a donné lieu à trois hypothèses successives, toutes fausses.
Le multiplicateur seul ne dit ni quelle branche l'a produit, ni si le niveau est légitime.

**Décision.** `regime_detail(mkt, t)` publie drawdown, recul du pic, niveau vs MM200 et pente
20 jours dans le diagnostic. Fonction purement descriptive : elle n'entre dans aucun calcul et
ne peut donc pas changer un poids.

**Conséquences.** La prochaine porte fermée sera lue, pas devinée. Coût : une ligne de
diagnostic et un appel de plus par exécution de production.
