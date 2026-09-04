# 02 — DECISIONS (ADR)

> 1 entrée par choix structurant. Format : contexte → décision → conséquences.

## ADR-0052 — Le stop suiveur ne protégeait pas les gains, il les COUPAIT (2026-09-02)

**Contexte.** `fast_swing` visait une cible à `rr = 6` fois le stop de 4 ATR, soit +24 ATR, avec
un suiveur ATR à 5. Le suiveur mordait donc presque toujours AVANT la cible : le 6:1 nominal
n'existait pas dans les faits, et c'est le couple (cible, suiveur) qui décidait — jamais la cible
seule, contrairement à ce que le paramètre laissait croire.

**La règle de décision a été écrite AVANT de voir le chiffre**, pour interdire la
rationalisation a posteriori : « maxDD dégradé de moins de 3 points → on bascule ; de plus de
6 points → on garde le suiveur, malgré le Sharpe ». C'est le point de méthode le plus important
de cet ADR : sans règle préalable, tout résultat se justifie après coup.

**Mesuré** (`scripts/sortie_lab.py`, cible figée à rr 6, empreinte 786 titres · 2 049 666 barres
· dernière 2026-09-01 · VIX RÉEL) :

| suiveur | payoff | marge | Sharpe | maxDD | DSR | esp./tr | net |
|---|---|---|---|---|---|---|---|
| **sans** | **3,21** | **25,6 %** | **0,53** | **−27,8 %** | **48,1 %** | **5,6** | **6 398** |
| trail 3 | 2,04 | 11,3 % | 0,42 | −21,8 % | 33,0 % | 1,8 | 3 900 |
| trail 5 (prod) | 2,82 | 14,0 % | 0,38 | −29,1 % | 26,9 % | 2,7 | 3 426 |
| trail 8 | 3,02 | 22,6 % | 0,45 | −26,0 % | 36,0 % | 4,7 | 5 300 |

Le maxDD ne se dégrade pas, il **s'améliore**. La seule objection sérieuse tombe, et le risque
PAR TRADE est inchangé : le stop initial à 4 ATR tient toujours.

**Décision.** `trail_atr = 0.0` en production. Le mécanisme est celui qu'annonçait la mesure de
concentration de l'ADR-0051 : l'avantage vit dans la queue droite, et tout ce qui la tronque le
détruit. Le suiveur était exactement cela — un tronqueur de gagnants déguisé en garde-fou.

**Ce qui n'est PAS prouvé.** L'écart de Sharpe (+0,15) reste sous le seuil détectable de ±0,27.
Ce qui décide est la COHÉRENCE de toute la famille — trail 3 très mauvais, trail 8 intermédiaire,
sans suiveur le meilleur — et l'accord de deux runs sur des jeux de données différents. Pas un
point isolé.

**Ce qu'on refuse de toucher, et c'est le second enseignement.** Le classement des CIBLES s'est
INVERSÉ entre les deux jeux : rr 6 meilleur le 01/09 (Sharpe 0,65), rr 9 meilleur le 02/09
(0,50 contre 0,38). Un optimum qui bouge d'un jour à l'autre est du bruit, pas un réglage. `rr`
reste à 6, et l'interaction (sans suiveur × rr 9) n'est pas explorée : chaque essai
supplémentaire relève le seuil du DSR sur tout le reste (ADR-0050).

**Conséquence opératoire : l'EMPREINTE.** Sur un appel au backtest identique au caractère près
(vérifié par diff), la même configuration a donné Sharpe 0,65 puis 0,38 à un jour d'écart. Rien
ne le disait. Les trois bancs affichent désormais titres, barres, dernière date et provenance du
VIX — cette dernière parce que `_index_closes` interroge le RÉSEAU quand la base est périmée, si
bien qu'un banc de décision pouvait comparer en silence un VIX réel à un VIX synthétique. **Deux
runs ne se comparent que si l'empreinte est identique.** Hypothèse du repli VIX émise puis NON
confirmée : le run du 02/09 affiche « VIX RÉEL ». La cause de l'écart reste le jour de données
ajouté, à confirmer.

## ADR-0051 — Le dimensionnement à RISQUE CONSTANT, adopté pour la robustesse et non pour la performance (2026-09-01)

**Contexte, et le chiffre qui a déclenché l'enquête.** Sur 477 trades réels, profit factor 1,19 —
lecture spontanée : « léger avantage ». Le profit factor privé des CINQ meilleurs trades valait
**0,89** : le système devenait perdant sans 1,05 % de ses trades. Il ne mesurait pas un avantage,
il mesurait cinq lignes.

**La mesure qui tranche entre queue épaisse et loterie de taille.** Le R d'un trade vaut
(sortie − entrée) / (entrée − stop) : son résultat en unités de RISQUE ENGAGÉ. Dimensionner à
risque égal revient à choisir qty telle que qty × (entrée − stop) soit constante, auquel cas le
P&L devient exactement proportionnel au R. Le t calculé sur les R n'est donc pas une analogie :
c'est le t qu'on aurait obtenu, à signaux identiques, à risque égal. Mesuré :

| | dollars | en R |
|---|---|---|
| t de l'espérance | 0,94 | 2,00 |
| profit factor sans les 5 meilleurs | 0,89 | 1,21 |

**La concentration n'était pas dans le signal, elle était dans la TAILLE des positions.** Cause
dans le code : `fast_swing` dimensionnait en notionnel, et `room` (l'exposition brute restante)
tronquait la ligne — la taille d'un trade dépendait de combien le carnet était plein ce jour-là.

**Ce que la contrefactuelle N'A PAS établi.** Le re-run complet (`scripts/sizing_lab.py`, banc
validé : sa ligne de référence reproduit la production au chiffre près — 477 trades, PF-5 0,89,
t 0,94, n effectif 427) donne à 0,5 % de risque par trade : PF-5 **0,89 → 1,15**, Sharpe
0,52 → 0,66 mais **p = 0,59**, et le net **−29 %** (9 642 → 6 863 $), espérance par trade de ~20
à ~6 $. Trois fractions essayées, donc même ce p est optimiste.

**Décision.** `risque_par_trade = 0,005` en production. Adopté sur le seul fait ÉTABLI — PF-5, qui
n'est pas une assertion statistique mais une propriété de la distribution réalisée — et **pas** sur
le Sharpe, qui reste indiscernable. L'avantage de net du notionnel vient de tailles plus grosses
sur cinq trades, non d'un meilleur signal : une chance de dimensionnement passée n'est pas une
espérance future, alors que la volatilité plus basse et l'indépendance aux cinq lignes sont
structurelles.

**Ce qu'on refuse de faire.** Affiner la fraction. 2 % est nettement pire (PF-5 0,81, Sharpe 0,23 —
lignes plus grosses, donc plus de troncatures), l'optimum est intérieur, et un balayage plus fin
sur 11 ans serait de l'ajustement a posteriori — exactement ce que l'ADR-0050 combat. 0,5 % est
aussi la fourchette institutionnelle usuelle (0,25–1 %).

**Conséquences.** Tous les chiffres publiés bougent : 477 → 1 168 trades, espérance par trade
divisée par ~3. Le défaut de la FONCTION reste `risque_par_trade = 0.0` : le comportement
historique est reproductible à l'identique, et rien d'autre ne change en silence. Sous 50 % de la
taille voulue, un trade est SAUTÉ plutôt que pris en miette — une miette paie les mêmes frais et
le même slippage pour une fraction de l'avantage.

**Méthode retenue, valable au-delà de ce cas.** Une contrefactuelle n'est pas une expérience. Ici
elle annonçait +114 % sur le t ; le re-run a donné un Sharpe indiscernable. C'est le re-run qui
décide. Et `t` monte MÉCANIQUEMENT avec le nombre de trades (espérance/écart-type × √n) : entre
variantes de cardinalités différentes il n'est pas comparable — seul le Sharpe l'est, et
l'exposition moyenne doit être publiée pour qu'on voie si les deux jouent le même levier.

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

## ADR-0048 — La stratégie est une DONNÉE hashée, pas une configuration éparpillée (2026-08-27)

**Contexte.** Les 26 et 27/08, trois divergences production/backtest ont été corrigées en un
jour : #347 (empilement positionnel vs alignement par date), #352 (sélection par qualité vs
ordre du dictionnaire), #353 (momentum mesuré à la barre 120 vs au dernier point). Cause
racine commune, et ce n'est aucune des trois : **il n'existait nulle part d'artefact disant
« voici la stratégie »**. Elle était répartie entre des valeurs par défaut de fonctions, des
variables d'environnement — `QUANT_LIVE_LITE=1` coupait `fundamentals`, donc changeait la
SÉLECTION D'UNIVERS — et des effets de bord. Deux chemins pouvaient donc diverger sans qu'aucun
diff ne le montre.

**Décision.** `packages/mandate` introduit le MANDAT : une définition déclarative, sérialisable,
dont l'identité est le SHA-256 de sa forme canonique. Ce hash entre dans chaque ordre, chaque
ligne de journal et chaque résultat de backtest — de sorte qu'on puisse toujours répondre à
« quelle définition exacte a produit cet ordre ». Vocabulaire : « mandat » est le terme
institutionnel exact et évite la collision avec `packages/strategies`, qui héberge les plugins
EXÉCUTABLES.

**Le découpage qui porte tout.** `meta` (nom, description, auteur, tags) est **hors identité**.
Renommer un mandat ou corriger une coquille ne doit pas rompre le lien d'audit avec les ordres
déjà émis — sinon toucher une description orpheline tout l'historique. Tout le reste
(contraintes, paramètres, règles de données, exécution) est sémantique et entre dans le hash.
Vérifié dans les deux sens par test.

**La forme canonique, sans quoi le hash ne prouve rien.** Tri des clés, sérialisation compacte,
flottant entier ramené à l'entier (`30.0` ≡ `30`), `-0.0` ramené à `0`, non-fini REFUSÉ. Choix
assumé : `0.3` et `0.1 + 0.2` hashent différemment — ce sont des nombres différents, et arrondir
en douce ferait collisionner deux configurations réellement distinctes, plus grave que
l'inverse. Corollaire : un paramètre de mandat se DÉCLARE, il ne se calcule pas.

**Format JSON, pas YAML.** YAML 1.1 coerce `no` en booléen et distingue mal `1` de `1.0`. Sur un
fichier dont le hash EST l'identité, ces conversions silencieuses la déplaceraient sans qu'on
touche au sens.

**Conséquences.** Une clé inconnue est refusée au chargement plutôt qu'ignorée : une clé ignorée
en silence n'entre ni dans le comportement ni dans le hash, et l'écart ne se voit nulle part —
exactement le mode de panne que ce module ferme. `config/mandats/preset_multi_actifs.json`
décrit le système RÉEL, et un test échoue dès qu'une valeur par défaut du preset change sans que
le mandat suive. Coût : toute modification de paramètre doit désormais passer par le mandat.

## ADR-0049 — Le moteur est une fonction PURE du mandat, et on le vérifie mécaniquement (2026-08-27)

**Contexte.** ADR-0048 donne une définition stable. Elle ne vaut rien si le moteur peut être
influencé par autre chose qu'elle. Or il l'était : une variable d'environnement décidait quelles
actions acheter.

**Décision.** Contrat `moteur(mandat, marché, as_of) -> poids cibles`, avec trois propriétés
vérifiables, chacune correspondant à un défaut RÉEL du dépôt :

| Propriété | Défaut qu'elle ferme |
|---|---|
| déterminisme | deux appels identiques doivent rendre le même résultat |
| indépendance à l'environnement | `QUANT_LIVE_LITE` changeait la sélection d'univers (26/08) |
| équivalence des chemins | #347, #352, #353 — rétablies une par une, à la main, après coup |

`packages/mandate/purete` implémente les trois. Le harnais bouscule volontairement les variables
suspectes puis **restaure exactement** l'état initial — un harnais qui contamine les tests
suivants serait pire que le défaut qu'il cherche, et c'est testé aussi.

**Tolérance.** La comparaison arrondit à 1e-9 : on compare des DÉCISIONS, pas le dernier bit d'un
flottant. Une réassociation d'opérations ne doit pas faire échouer le test pour un écart qui ne
change aucun ordre envoyé. Un test vérifie que la tolérance n'avale pas pour autant un écart
significatif.

**Conséquences.** Le harnais attrape aujourd'hui la classe de défaut qui a coûté trois PR ; il
n'est pas encore branché sur le preset lui-même — c'est la migration suivante, et elle touche du
code de production tout juste stabilisé. Elle se fera dans une PR dédiée, pas dans celle-ci.

## ADR-0050 — On ne SPÉCIFIE pas un Sharpe : on le mesure, dégonflé du nombre d'essais (2026-08-27)

**Contexte.** Proposition initiale : « l'IA te sort la stratégie optimale — tu peux demander un
Sharpe de 2,3 ». C'est une spécification par le RÉSULTAT, et une machine à surapprendre.

**Le chiffre qui tranche, et il vient du dépôt.** `research/sharpe_diff.seuil_detectable` établit
que 126 pas ne résolvent que ~+0,14 de Sharpe (ADR-0039). Un système incapable de distinguer 1,35
de 1,49 ne peut pas livrer « 2,3 » comme contrat. Pire : si une boucle génère des candidats et
garde ceux qui atteignent la cible, le maximum de N tirages bruités croît en √(2 ln N) — sur 100
essais, ~2,5 écarts-types « gratuits ». On obtiendrait 2,3, en backtest, sans aucun alpha.

**Décision.** Le schéma de mandat REFUSE toute cible de résultat en entrée (`sharpe`, `sortino`,
`calmar`, `rendement`, `dsr`…). Le refus est structurel, pas un conseil en docstring. Ce qui est
spécifiable est ce qu'on CONTRÔLE : `drawdown_max`, `turnover_max_annuel`, `levier_max`,
`liquidite_min_adv`, `nb_lignes_min`, univers autorisé. Ces grandeurs restent parfaitement
légitimes en SORTIE, avec leur barre d'erreur et le nombre d'essais.

**Ce que le dépôt avait DÉJÀ, et que j'ai commencé par redévelopper.** `portfolio/psr.py`
(PSR + DSR, avec la gestion du piège de périodicité annualisé/par-période — audit du 20/08),
`research/ledger.py` (registre JSONL, `trial_count`, `deflation_params`), `research/gate.py` (le
verdict). J'en avais écrit une version parallèle, moins bonne. Elle a été supprimée. **Seul
Benjamini-Hochberg manquait réellement** — vérifié par recherche, absent du dépôt, et réclamé en
P0 par le TODO pour le criblage de paires.

**Décision complémentaire.** `packages/research/fdr.py` — BH seul, et le nombre de candidats
testés publié AVEC le verdict. Le DSR déflate UN candidat du nombre d'essais ; il ne répond pas à
« parmi N verdicts positifs simultanés, combien sont du bruit ? ». BH plutôt que Bonferroni : sur
des candidats corrélés, Bonferroni ne laisse rien passer.

**Conséquences.** L'ordre de construction est fixé : mandat hashé → moteur pur → comptage des
hypothèses → **et seulement ensuite** un LLM qui propose des mandats. Le LLM en dernier, non par
prudence de principe, mais parce que sans les trois premiers il amplifie le bruit au lieu de
produire du signal.

**Corollaire de méthode.** Avant d'écrire un module, chercher ce qui existe. Le dépôt compte 28
paquets ; j'ai dupliqué PSR/DSR et un registre d'hypothèses parce que j'ai conçu avant de lire.

---

## ADR-0053 — Le cœur change de COMPOSITION, jamais de TAILLE (2026-09-02)

**Contexte.** Question posée : un top-7 plutôt qu'un top-10 améliorerait-il la performance ?
La mesure existante répond déjà non — la concentration dégrade le maxDD de −19,5 % à −73,6 %
sans gagner de Sharpe. Le compte réel, lui, affiche N effectif 1,5 : le portefeuille se
comporte comme une position et demie. Le problème n'est pas le nombre de lignes, c'est leur
corrélation.

**Décision.** Le banc `make coeur-multi` garde la part de cœur à **50 %, identique à la
production**, et ne fait varier que sa composition (QQQ + obligations longues + or). Tout
écart mesuré est donc imputable à la corrélation, à rien d'autre. Quatre variantes sont
**figées dans le code** avant toute mesure et comptées dans la déflation du DSR ; les poids
sont une convention (un 60/40 incliné croissance), jamais un optimum ajusté.

**Règle d'acceptation, écrite avant le run.** Bascule SI ET SEULEMENT SI : (a) ΔSharpe > 0
avec p < 0,05 au test apparié de Jobson-Korkie/Memmel, (b) maxDD non dégradé, (c) DSR ≥ 50 %.
Si (a) échoue on ne bouge pas, quel que soit le CAGR. Si (a) passe et (b) échoue, on ne bouge
pas non plus : acheter du Sharpe avec un drawdown plus profond contredit la raison même de
construire ce cœur. Un maxDD amélioré de plus de 5 points à Sharpe indiscernable est remonté
comme « réduction du risque », PAS comme feu vert.

**Conséquences.** Le cœur multi-actifs paie 5 bps de rééquilibrage mensuel, le cœur QQQ zéro
(buy-and-hold) : la comparaison est défavorable au nouveau venu, et c'est le sens d'erreur
qu'on accepte. Les séries des diversifiants sont alignées **par date** dans le snapshot, à la
source — jamais empilées par position.

---

## ADR-0054 — Un cahier des charges externe se CÂBLE sur l'existant, il ne se recode pas (2026-09-02)

**Contexte.** Une spec complète de robot swing institutionnel (structure fractale 1W/1D/1H,
SFP, OTE, filtre ML, DDM, ratios de survie) demandait « le squelette architectural complet ».
Écrit à neuf, ce squelette aurait dupliqué le DDM, les stops ATR, la validation croisée
purgée, l'IC de Spearman et la promotion de modèle — tous déjà présents et testés.

**Décision.** Quatre modules de primitives + une façade d'orchestration
(`strategies/moteur_swing`, classes `MarketStructureEngine` et `RiskManager` aux noms
demandés). Les classes composent ; elles ne calculent presque rien. Un tableau de
correspondance spec → module figure en tête du fichier, pour que le lecteur voie tout de
suite ce qui est neuf et ce qui ne l'est pas.

**Ce qui est refusé, explicitement.** La jambe 1H/4H est câblée mais la base est
QUOTIDIENNE : `raffiner_entree` renvoie « indécidable » et jamais « prêt » quand aucune barre
intraday n'est fournie. Renvoyer un feu vert par défaut ferait disparaître un filtre de la
spec en silence — le système se comporterait comme s'il avait vérifié quelque chose.

**Les cibles de la spec ne sont pas des résultats.** PF ≥ 1,75 · Sortino ≥ 2,0 · maxDD ≤ 12 %
· UI ≤ 4,5 · R² ≥ 0,90 sont des seuils écrits sans avoir vu ces données. Le système mesuré
affiche PF 1,08, Sortino 0,88, maxDD −25,5 %. L'écart n'est pas un défaut d'implémentation :
c'est la distance entre un cahier des charges et une mesure. Aucun de ces seuils n'est câblé
comme critère d'acceptation ; les publier comme atteints serait le seul vrai échec.

**Conséquence défavorable acceptée.** SFP, order block et cassure de structure existent
maintenant en deux exemplaires (`indicators/liquidite_ict` en primitives as-of-`i`,
`strategies/institutional_price_action` en plugin de signal). Consolider est une dette P2
déclarée, pas un travail fait.

---

## ADR-0055 — Le stop ne bouge que sur la structure ; l'ordre d'évaluation est pessimiste (2026-09-02)

**Contexte.** Le bloc de sortie de la spec swing interdit le breakeven de confort et exige
une sortie de temps à 15 séances. C'est aussi ce que `sortie_lab` a mesuré le 02/09 par un
tout autre chemin : le suiveur à 5 ATR coupait la queue droite et détruisait l'avantage
(payoff 2,82 vs 3,21 sans lui). Deux raisonnements indépendants, une seule conclusion.

**Décision 1 — invariant du stop.** `ExitEngine` ne déplace le stop QUE sur un invalidant
structurel : pour un long, un creux confirmé plus haut que le stop courant, lui-même validé
par un sommet confirmé POSTÉRIEUR. Aucune branche du code ne lit le prix d'entrée, le gain
courant ou un multiple d'ATR. Le garde-fou est doublé : la détection le refuse, et
`appliquer` ignore tout recul même demandé explicitement — une règle de sécurité qui
n'existe qu'à un endroit finit contournée.

**Décision 2 — ordre d'évaluation pessimiste.** Stop, puis cible, puis temps, puis partielle.
Une barre quotidienne qui touche le stop ET la cible ne dit pas laquelle est venue en
premier. Retenir le stop est l'hypothèse défavorable ; retenir la cible fabriquerait de la
performance à partir d'une ambiguïté de données.

**Décision 3 — la cible retient le plus exigeant des deux critères**, sommet majeur OU
plancher en R. Le sommet seul accepterait des trades à 1,2 R ; le R seul viserait un prix que
rien n'attire.

**Ce qui est assumé comme approximation.** Le CVD suppose des transactions signées ; des
barres OHLCV n'en ont pas. Le module utilise le proxy « close location value × volume » et
porte le nom `cvd_proxy`. Une divergence est ici un fait de prix et de volume — pas une
preuve d'absorption institutionnelle. Le renommer en `cvd` serait la seule vraie faute.

**Ce qui est refusé.** La borne « 2 jours » n'est pas transformée en immobilisation : elle
est reportée et ne bloque jamais une sortie que le marché offre. Une borne basse en verrou
serait un coût déguisé en protection.


## ADR-0056 — Le fill d'ouverture vient des ORDRES EXÉCUTÉS, jamais de la position (2026-09-03)

**Contexte.** `run_live._journal_opens` lisait le prix et la quantité d'entrée dans la position
du courtier, interrogée juste après l'envoi de l'ordre. Mesure du 03/09 sur le compte réel :
87 symboles achetés, 57 couverts par le journal, 30 incomplets (AVAX 626 unités journalisées
contre 1 239 achetées). La position est une photo d'état, pas une trace d'opération : elle peut
n'être pas encore rafraîchie — l'achat est alors introuvable et perdu, le message « capturé au
prochain run » étant faux puisque rien ne le capture — et quand elle est lisible elle porte la
quantité TOTALE et le prix de revient MOYEN, pas l'achat du jour.

**Décision.** La source primaire du fill d'ouverture est l'historique des **ordres exécutés du
jour**, agrégés par symbole canonique (quantité et VWAP). La position ne sert que de repli, et
ce repli est déclaré comme une approximation. Rien n'est écrit si aucune des deux sources ne
répond.

**Conséquences.** Un run tardif retrouve les achats de la journée : le journal cesse de dépendre
de la latence du courtier. Le lot décrit l'opération qu'il prétend décrire. Le repli reste
possible pour un courtier qui ne publie pas d'historique d'ordres, au prix d'un prix de revient
moyen — c'est un choix assumé, pas un défaut silencieux.

## ADR-0057 — On complète les ENTRÉES avant de réparer les SORTIES (2026-09-03)

**Contexte.** Deux jours de réparation du journal portaient sur les sorties : lots orphelins,
fermetures sans identité, résidu inexpliqué. Elles ne pouvaient pas converger, parce qu'un achat
jamais journalisé n'a pas de lot — donc pas de sortie possible, et la vente correspondante reste
sans contrepartie quoi qu'on fasse en aval.

**Décision.** Une réparation de registre se fait dans l'ordre du flux : `completer-ouvertures`
(reconstitue les achats manquants depuis les fills), puis `reconcilier-journal` (ferme avec les
ventes réelles), puis `diag-journal` (vérifie). Les lots reconstitués sont écrits en `legacy=1`,
parce que leurs features de décision n'ont jamais été capturées et ne peuvent plus l'être : c'est
le sens exact du drapeau, et les mettre en `legacy=0` gonflerait de trades aveugles la
statistique affichée qu'on cherche à assainir. Leur prix de revient est le VWAP des fills **non
couverts** — obtenu en consommant les fills en FIFO à hauteur de ce que le journal connaît déjà —
et non le VWAP de tous les achats du symbole, qui mélangerait le couvert et le manquant.

**Conséquences.** L'idempotence du réconciliateur devient une idempotence en QUANTITÉ : écarter
un fill de vente dès son premier usage condamnerait à rester ouverts pour toujours les lots
reconstitués après coup, dont la vente existe mais a déjà été marquée consommée. On compte donc
les unités fermées par fill et on rejoue le reste. Deux refus explicites subsistent : rien n'est
écrit pour un courtier injoignable, et un écart où le journal en sait PLUS que le courtier est
signalé sans être « corrigé » — supprimer des lots pour faire coller les chiffres ne répare rien.

## ADR-0058 — Le panneau publie son PÉRIMÈTRE, il ne l'élargit pas (2026-09-03)

**Contexte.** `/api/journal` lit `all(legacy=False)`. Après la réparation du 03/09, ce périmètre
affichait +6 260,82 $ de réalisé et 70 % de réussite, quand le compte avait subi +569,31 $ et
56 % : le filtre masquait 266 lots et −5 691,51 $. Aucun des deux chiffres n'est faux. Ce qui
l'était, c'est de n'en publier qu'un et de le laisser lire comme la performance du compte.

**Décision.** Le périmètre affiché reste `legacy=0`, et l'écart avec le total est publié à
côté, chiffré (`perimetre_affiche`). On ne verse pas les lots `legacy` dans la statistique
affichée : ce sont des fills importés sans features de décision, et les y mêler rendrait
inutilisable pour la calibration ML le chiffre même qui la sert.

**Conséquences.** Le lecteur voit d'un coup d'œil que le panneau décrit les trades pilotés par
le système et non le compte. La correspondance avec la courbe d'équité redevient vérifiable au
lieu d'être supposée. Un troisième chiffre apparaît sur la page ; c'est le prix d'une lecture
qui ne se trompe plus de question.

## ADR-0059 — Une mesure qui infirme n'infirme que ce qu'elle a mesuré (2026-09-03)

**Contexte.** `_doublons` cherchait des lots OUVERTS de mêmes titre, quantité, prix et jour, et
répondait « aucun doublon ». La conclusion « le journal n'écrit pas en double » en avait été
tirée, et le sujet clos. Après la réparation, le rapport quantité-journal / quantité-achetée
vaut 2,000000 sur dix symboles vérifiés parmi quarante. Les deux copies portent des identifiants
différents, l'une peut être fermée, et leurs drapeaux `legacy` peuvent différer : trois
conditions hors du champ du test. Troisième occurrence de ce schéma cette semaine.

**Décision.** Une mesure ne réfute que l'énoncé qu'elle teste, et son périmètre doit être écrit
à côté de son verdict. `_origine_du_double` VENTILE (par drapeau, par préfixe d'identifiant) au
lieu de conclure, et ne supprime rien : il rend la cause lisible et laisse la décision à
l'humain qui lit le chiffre.

**Conséquences.** Un bloc de diagnostic supplémentaire à chaque `make diag-journal`. En échange,
la question « une seule écriture ou deux chemins ? » se tranche sur un chiffre plutôt que sur
une lecture de code, et l'on ne retire aucune ligne d'un registre avant de savoir laquelle.

## ADR-0060 — Une sortie ne peut pas précéder son entrée (2026-09-03)

**Contexte.** `reconcilier_journal._plan` appariait chaque vente au plus ancien lot du symbole
sans jamais regarder la date d'entrée de ce lot. Signalé sur le compte réel : DUOL portait une
entrée au 03/09 et une sortie au 01/09. Le round-trip ainsi fabriqué calculait son P&L sur un
prix de revient POSTÉRIEUR à la sortie — un chiffre qui ne correspond à aucune opération.

**Décision.** Le FIFO ne s'applique qu'aux lots antérieurs à la vente. La comparaison se fait au
JOUR et non à la seconde : le lot porte l'instant où le run l'a écrit, le fill celui de
l'exécution, et ces deux horloges ne sont pas comparables — trancher à la seconde refuserait des
aller-retours réels. Une date illisible d'un côté ou de l'autre fait REFUSER l'appariement plutôt
que le supposer valide. Le FIFO saute le lot trop récent au lieu de s'arrêter dessus.

**Conséquences.** Aucun round-trip à chronologie impossible ne peut plus être créé. La garde ne
rétroagit pas sur ceux déjà écrits : `_sorties_avant_entree` les compte au diagnostic, et leur
reprise suppose un plan complet — savoir à quel lot la vente aurait dû s'apparier ne se décide
pas ligne à ligne.

## ADR-0061 — Une opération qui n'a pas eu lieu se RETIRE ; elle ne se corrige pas (2026-09-03)

**Contexte.** La règle du dépôt est de ne jamais réécrire un enregistrement mais de poster une
écriture de correction. Elle est juste, et elle vise une VALEUR fausse. Mesuré le 03/09 : 33 des
52 lots « ouverts » portaient le symbole, la quantité et le prix EXACTS d'un fill de VENTE — des
sorties écrites à l'endroit des entrées. Leur valeur n'est pas fausse ; l'opération n'a pas eu
lieu dans ce sens. Les garder revient à publier des positions que le compte n'a jamais eues.

**Décision.** Ces lignes sont RETIRÉES (`SqliteTradeJournal.supprimer`), et seulement celles que
désigne un fill de vente unique de mêmes symbole, quantité et prix. Deux archives survivent au
retrait : une sauvegarde horodatée de la base, et un JSON portant chaque ligne retirée AVEC le
fill qui l'a désignée — un retrait sans sa preuve n'est pas rejugeable. Ce JSON contient des
fills réels : il est gitignoré, le dépôt étant public.

**Alternative écartée.** Fermer ces lots à leur prix d'entrée. Cela produirait un aller-retour à
0,00 $ qui n'a jamais existé et gonflerait le nombre de trades : on remplacerait une fausse
position par un faux trade, ce qui est pire, parce que moins visible.

**Conséquences.** Le critère strict (fill unique) sous-estime : une vente exécutée en plusieurs
fills ne sera pas appariée et son lot restera ouvert et signalé. C'est la seule direction
d'erreur acceptable pour une mesure qui décide d'un retrait — on préfère un registre encore
imparfait à un registre nettoyé sur une présomption.

## ADR-0062 — « En retard » et « arrêtée » sont deux états, pas un seul (2026-09-03)

**Contexte.** Le détecteur de fraîcheur macro déclarait « série arrêtée — ne reflète plus la
situation actuelle » dès 3× la cadence observée. Le Bund (OCDE, taux longs) portait ce label
avec 94 jours de retard contre un seuil de 93 : un dépassement d'UN jour, soit 3,03× la
cadence. Le cas qui avait motivé la règle — chômage zone euro — valait 43×. Cette série publie
par ailleurs avec un décalage structurel de deux mois : elle rebasculerait en « arrêtée » à la
fin de chaque trimestre, puis en sortirait à la publication suivante.

**Décision.** Deux seuils au lieu d'un. Au-delà de 3× la cadence, la publication est EN RETARD
et la série vit. Au-delà de 12× — un an de silence sur du mensuel — la série est ARRÊTÉE. Le
champ `perimee` reste vrai dès le retard, pour qu'aucun appelant existant ne cesse de signaler ;
le nouveau champ `statut` porte la nuance pour qui sait la lire.

**Conséquences.** Une alerte qui clignote au rythme du calendrier de publication apprend à être
ignorée : c'est le coût réel d'un seuil unique, et il est plus élevé qu'un faux négatif ici,
puisqu'une série vraiment morte reste détectée par le second seuil. Le mot « arrêtée » redevient
utilisable parce qu'il ne désigne plus qu'une chose.

## ADR-0063 — Une page hors de la barre de navigation n'existe pas (2026-09-03)

**Contexte.** L'audit « simplicité radicale » avait ramené la navigation à trois groupes. Les
pages absorbées restaient routables — URL directe, liens contextuels, ⌘K — ce qui semblait
suffisant. Signalé le 03/09 : « je ne retrouve plus l'onglet des news ». `/sentiment` était
intacte et fonctionnelle ; simplement introuvable pour qui ne connaît pas son adresse.

**Décision.** « Routable » n'est pas « accessible ». Une page que l'utilisateur consulte
régulièrement doit figurer dans un menu. `/sentiment` (actualité marché, secteur et positions
réelles) et `/events` (résultats trimestriels et IPOs) rejoignent « Marché ».

**Conséquences.** Onze pages restent hors de la barre. Ce n'est pas un oubli mais le résultat
d'un arbitrage assumé : elles y restent jusqu'à décision explicite, plutôt que d'être réinsérées
une par une au fil des signalements — ce qui déferait l'audit sans jamais le rediscuter.

## ADR-0064 — Une seule politique de fusion des sources, et elle est tracée (2026-09-04)

**Contexte.** Deux fonctions fusionnaient les mêmes bases de prix selon des règles opposées :
`_load_prices` gardait le premier provider (`setdefault`), `merge_bars` gardait le dernier
(`target[jour] = …`). Mêmes bases, mêmes dates, deux historiques pour le même actif selon la
fonction qui le demandait — **0,71 %/an d'écart** mesuré sur le cœur QQQ. Aucune des deux ne
savait qu'elle contredisait l'autre.

**Décision.** Une implémentation unique (`packages/data/fusion_sources`), et c'est le PREMIER
provider qui prime. La raison est écrite : la base longue porte un historique AJUSTÉ, la couche
de mise à jour est brute ; la laisser écraser insérerait une discontinuité raw/ajusté au milieu
de l'historique, dont les rendements de part et d'autre ne sont plus comparables. La fraîcheur
survit à la règle, les dates récentes étant exactement celles qui manquent à la base longue.
Chaque jour retenu porte le NOM de la source qui l'a fourni.

**Conséquences.** Une copie d'une politique diverge toujours : c'est ce qui s'est produit ici,
et l'unique implémentation est ce qui l'empêche de se reproduire. Le lignage transforme « d'où
vient cette barre ? » en lecture. `make diag-fusion` chiffre les désaccords entre bases là où
elles se recouvrent — un désaccord ne dit pas laquelle a raison, il dit que la priorité change
le résultat.

## ADR-0065 — Un scan est un ESSAI : il se compte, ou le Sharpe déflaté ment (2026-09-04)

**Contexte.** Un scanner piloté en langage naturel balaie 200 titres en une minute. Chaque
variante de seuil est un test supplémentaire, et vingt tests non enregistrés font passer pour
significatif ce qui ne l'est pas. Le dépôt possède le remède (`ledger` compte les essais,
`deflation_params` en tire le `N` du DSR) mais rien ne reliait le scanner au registre.

**Décision.** Tout scan produit un enregistrement au ledger, sous le facteur `scan_ad_hoc` et
au statut `exploratoire` — jamais « validé » : un scan ne valide rien. L'empreinte des critères
NORMALISÉS (triés) sert de clé d'idempotence. Les critères sont structurés et validés contre une
liste fermée d'opérateurs ; aucun parseur de langage naturel n'entre dans la couche de recherche,
traduire la phrase reste le travail du modèle appelant.

**Conséquences.** Le compte d'essais était jusqu'ici SOUS-estimé — les idées testées à la main ne
laissent aucune trace — donc le DSR déflatait trop peu. Un scanner qui enregistre le rend honnête
pour la première fois : la fonctionnalité qui menaçait la statistique devient ce qui la répare.
L'idempotence est obligatoire dans les deux sens : rejouer une question ne la repose pas, mais
deux seuils différents sont deux essais.

## ADR-0066 — On ne branche pas DuckDB sans l'avoir mesuré (2026-09-04)

**Contexte.** `make_bars_repository` arbitre entre sqlite et duckdb et n'a **aucun appelant**. Le
dépôt DuckDB (79 lignes, export Parquet partitionné) porte lui-même la mention « écrit pour
l'environnement de prod ; non exécuté hors-ligne ». Le chemin colonnaire est conçu, pas branché,
et la question « irait-il plus vite ? » n'a jamais reçu de chiffre.

**Décision.** Aucun basculement avant mesure. `make bench-backend` chronomètre la LECTURE — le
coût qui pèse réellement sur les bancs — sur la vraie base, en lisant le MÊME fichier par les
deux moteurs (comparer deux bases différentes mesurerait leur contenu, pas le moteur). La règle
est écrite avant le run : gain médian < 1,5× → on reste sur SQLite ; ≥ 1,5× → le basculement se
justifie, mais reste conditionné à l'unification de `DBPriceProvider` et `BarsRepository`.

**Conséquences.** Ces deux abstractions sur la même donnée sont la vraie raison pour laquelle la
fabrique n'a jamais eu d'appelant : « brancher DuckDB » n'est pas un changement de variable, c'est
un refactor, et il doit être payé par un chiffre. Sans DuckDB installé, le banc ne rend aucun
verdict et le dit — il ne suppose pas.

## ADR-0067 — Sans les deux calendriers, on refuse de conclure (2026-09-04)

**Contexte.** `compute_attribution` appariait la courbe du preset et celle de QQQ par position
(`min(len)` puis `[-n:]`). Les deux suivent des calendriers différents — univers négociable
contre indices — et le résultat publié était bêta 0,006, corrélation 0,008 pour un portefeuille
long-only d'actions américaines. La racine était en amont : `_index_closes` jetait les dates que
`_index_series` lui rendait, une ligne avant qu'elles servent.

**Décision.** Les dates voyagent avec les cours (`_index_closes_dates`, `qqq_dates` au snapshot)
et l'attribution apparie par date via `apparier_deux_series`. Quand un calendrier manque, elle
renvoie `available: False` avec un motif au lieu de retomber sur l'appariement positionnel.

**Conséquences.** Un résultat absent se voit ; un résultat faux se lit — c'est pourquoi le repli
positionnel est refusé plutôt que conservé « au cas où ». La contre-épreuve compte autant que le
correctif : un décalage de fin d'historique ne reproduit PAS le défaut (les deux séries finissant
le même jour, le positionnel tombe juste), seuls des trous intérieurs le montrent — 0,29 contre
1,00 sur le même actif. C'est aussi pourquoi le bug est resté invisible si longtemps.

## ADR-0068 — Une seule définition de la déviation baissière (2026-09-04)

**Contexte.** Trois conventions coexistaient et publiaient trois Sortino pour le même
portefeuille. Mesuré sur 2 520 rendements : la définition donne 0,008314 ; l'écart-type des
négatifs seuls 0,007369 (Sortino ×1,128) ; l'écart-type de min(r,0) 0,006979 (×1,191). Le backlog
annonçait 1,04× — l'écart réel est trois à cinq fois plus grand, et les deux erreurs flattent.

**Décision.** `packages/portfolio/deviation` porte la définition (Sortino & Price 1994 : racine
de la moyenne des carrés sous le seuil, sur le nombre TOTAL d'observations), en Python pur parce
que `analytics` et `company_report` évitent délibérément numpy. Quatre appelants y délèguent.

**Conséquences.** Diviser par le nombre de négatifs était la plus grave des deux erreurs : le
ratio cessait de dépendre de la FRÉQUENCE des pertes, ce que Sortino existe pour mesurer. Les
Sortino publiés vont baisser de 12 à 19 % selon la page — ce n'est pas une régression, c'est la
disparition d'une flatterie.


## ADR-0069 — Un chiffre ne voyage pas sans son biais (2026-09-04)

**Contexte.** Le cœur momentum sectoriel affichait 55,5 % de CAGR sur 9,4 ans, DSR 100 %.
L'audit du 04/09 a séparé trois causes par la mesure : coûts absents (0,64 point de CAGR — réel
mais mineur), look-ahead dormant dans la MM50 (jamais lu, réveillable en silence), et univers de
survivants. La troisième domine : `build_snapshot` retire tout titre dont la dernière barre a
plus de dix jours, donc tous les délistés, avant que le moindre backtest ne tourne.

**Décision.** Le statut du biais est ATTACHÉ au résultat (`biais_survivant`), pas publié à côté.
Il mesure les délistés réellement présents dans le panneau, et non — comme `survivorship_audit` —
le rapport des délistés connus au nombre d'actifs : ce dernier annonce « corrigé (partiel) » sur
un univers de survivants purs, parce qu'il répond à une autre question. Les coûts sont appliqués
(5 bps, convention du dépôt) et publiés. Le préfixe de la moyenne mobile vaut NaN plutôt que la
moyenne de la première fenêtre.

**Conséquences.** Le biais n'est pas corrigé — cela exige l'historique des délistés, que le dépôt
sait sous-échantillonné — mais il n'est plus séparable du chiffre qu'il conditionne. Un CAGR
séparé de son biais se lit comme un résultat ; c'est ce qui s'est produit ici pendant que l'audit
existait, disponible et jamais joint.


## ADR-0070 — Le gate de publication refuse l'impossible, pas les mauvaises nouvelles (2026-09-04)

**Contexte.** Le site a publié CAGR −100 %, gain total −100 %, pire baisse −100 %, avec un Sharpe
de 0,25 et un Sortino de 0,18. Le gate `check_build` était vert : fichiers présents, volumineux,
datés du jour. Il ne regardait jamais les nombres. La cause était `0 * nan = nan` en numpy, dans
le calcul du rendement quotidien du preset — un titre au poids ZÉRO suffisait à annuler la courbe
dès qu'il lui manquait un cours.

**Décision.** Le gate contrôle désormais la PLAUSIBILITÉ, selon deux règles qui sont des
contradictions et non des seuils : un capital anéanti ne peut pas coexister avec un ratio
positif ; une courbe d'équity publiée ne peut pas contenir de `null`.

**Pourquoi pas des seuils.** « CAGR < −50 % » serait un jugement sur la performance. Une
stratégie a le droit de perdre beaucoup, et un gate qui refuse les mauvaises nouvelles finit par
cacher les vraies. Une contradiction ne dépend d'aucune opinion. Vérifié : une perte sévère
cohérente passe, un anéantissement avec Sharpe négatif passe, le cas du 04/09 est refusé.

**Conséquences.** La seconde règle vaut mieux que la première : elle attrape la cause (le trou)
plutôt que le symptôme (le chiffre absurde), et elle vaut avant même de savoir ce que le trou
signifie. Le module vit dans `packages/` pour être exerçable en test — un gate qu'on ne teste pas
est un gate qu'on découvre en panne le jour où il compte.


## ADR-0071 — La cohérence du site est un contrat testé, pas une promesse (2026-09-04)

**Contexte.** Demande explicite : « plus aucune erreur ni incohérence » entre local, en ligne,
ordinateur, téléphone et onglets. Une promesse de ce type ne peut pas être tenue par un
engagement verbal — ce carnet est plein d'affirmations qu'il a fallu retirer parce que le code ne
les tenait pas.

**Décision.** L'exigence devient un contrat vérifié : `coherence_site` (invariants entre courbes,
dates et statistiques) et `gate_publication` (contradictions arithmétiques) tournent dans
`check_build`, donc dans le workflow Pages, et FONT ÉCHOUER le déploiement. Un test permanent
compare les routes appelées par le front aux fichiers écrits par le build statique : une route
manquante rendrait 404 en ligne tout en marchant en local.

**Le principe qui gouverne chaque règle : aucun faux positif.** Un gate qui crie au loup finit
désactivé — le détecteur de fraîcheur macro de ce dépôt se trompait 4 fois sur 5 et « apprenait à
être ignoré ». Toute règle est donc une impossibilité vérifiable sans connaître l'intention, et
chaque règle est accompagnée de tests « doit PASSER » qui protègent sa crédibilité.

**Ce qui est inventorié et non bloqué.** Les dates d'arrêté diffèrent légitimement entre domaines
(la crypto cote le week-end). Le build les recense dans son log au lieu d'en faire une règle qui
échouerait chaque samedi.

**Conséquences, et limite assumée.** Le dispositif garantit la cohérence INTERNE des chiffres
publiés et la parité local/en-ligne. Il ne garantit pas qu'un chiffre soit juste au sens
économique — aucun automate ne le peut. Et le journal réel reste local-only : les chiffres de
compte du site public ne sont pas ceux du Mac. Ce n'est pas une incohérence mais un périmètre,
désormais affiché sur la page concernée.

## ADR-0072 — L'appariement par date est une règle de dépôt, pas un correctif ponctuel (2026-09-04)

**Contexte.** Question de l'utilisateur devant le tableau de bord : « contribution alpha, est-ce
correct ? Il me semble élevé. » 1 072,2 % de contribution alpha, bêta 0,037, corrélation 0,031
vis-à-vis de QQQ, pour un portefeuille long-only d'actions américaines. Le chiffre à regarder
n'était pas la contribution mais le bêta : une contribution alpha, c'est le RÉSIDU `r − β·b`.
Un bêta écrasé bascule mécaniquement tout le rendement du côté « alpha ».

L'ADR-0067 avait corrigé `compute_attribution` (miroir Obsidian) le matin même. Le panneau web ne
passe pas par là : il lit `/api/analytics`, donc `packages/reporting/analytics.py`, qui faisait
exactement la même chose — `m = min(len(r), len(b))` puis `r[-m:], b[-m:]`. **Cinquième
occurrence.** Une sixième a été trouvée dans la foulée : `_bench_series` posait le i-ème cours du
S&P sur la i-ème date du portefeuille — la courbe de comparaison tracée sous l'equity.

**Mesure, pas déduction.** Deux fois la même courbe, 400 séances, cinq séances retirées du
calendrier du benchmark (1,25 %) : par date bêta 1,200 et corrélation 1,000 ; par position bêta
0,345 et corrélation 0,288. Un peu plus de 1 % de calendrier suffit à détruire 71 % du bêta. Sur
un levier pur 1,2× (alpha nul par construction), la part « alpha » passe de 5,5 % à 47,6 %.

**Décision.** Toute comparaison entre deux séries de calendriers différents passe par
`apparier_deux_series` (deux séries) ou `aligner_par_date` (N séries). Le résultat publié PORTE la
manière dont il a été obtenu : `attribution()` expose `alignement` (`"date"` / `"position"`) et
`n_observations`, et le tableau de bord affiche un avertissement orange quand l'appariement est
positionnel. Sans calendrier commun suffisant, `available: False` + motif.

**Conséquences.** Six occurrences en un jour disent que la revue au cas par cas ne suffit pas :
`min(len(a), len(b))` sur deux séries de sources différentes est à traiter comme un défaut par
défaut, pas comme un choix. L'inventaire des occurrences restantes (indice équipondéré `eqw`,
horodatage de `fast_swing`, `_align` de `packages/portfolio/benchmark`) est au TODO en P1 : elles
sont identifiées par lecture du code, pas encore MESURÉES sur données réelles, et on ne remplace
pas un chiffre publié par un autre sans l'avoir mesuré.

## ADR-0073 — Le banc de sortie ne mesure pas ce qui tourne en production (2026-09-04)

**Contexte.** Question de l'utilisateur : « plutôt qu'un rebalancement quotidien, ne
vaudrait-il pas mieux tenir les positions jusqu'au TP ou au SL ? » Trois mesures ont été
nécessaires pour répondre, et chacune a d'abord donné un faux résultat qu'il a fallu
corriger (comptage des tranches, fermetures administratives). Photo finale du journal
réel du Mac mini, décisions du SYSTÈME seulement : **6 positions closes en 57 jours,
détention médiane 0,1 jour, taux de gain 33 %, t = +0,92 (non significatif), capture
−22 % sur 5 positions mesurables**.

**Le vrai constat n'est pas statistique, il est structurel.** `sortie_lab` — le banc où
l'on règle `rr` et le suiveur ATR, et qui annonce des détentions de 42 à 48 jours —
rejoue `fast_swing_backtest` : stop 4 ATR, cible en R-multiples, suiveur. Le chemin de
production, lui, est `run_live.py` → poids cibles `preset risk-parity + DD-target`
(`apps/api/snapshot.py`). **Ce sont deux moteurs différents.** La production ne lit ni
`rr`, ni le suiveur, ni un stop ATR : elle n'a aucune notion de TP ou de SL, et son seul
motif de sortie est le rebalancement. Passer `rr 6 → rr 9` ou retirer le suiveur dans le
banc ne changerait **pas un seul ordre** envoyé en production.

**Décision.** Ne pas régler les paramètres de `sortie_lab` en croyant agir sur la
production. Les deux systèmes sont nommés séparément partout où ils apparaissent, et
tout résultat du banc porte désormais la mention du moteur qu'il mesure. La question
« tenir jusqu'au TP/SL » n'est pas un réglage : c'est le choix de faire tourner en
production un autre moteur que celui qui y tourne — un changement gaté, à valider pour
lui-même, pas un ajustement.

**Conséquences.** L'instabilité relevée le même jour sur `sortie_lab` (« sans suiveur »
à Sharpe 0,50 sur les données au 04/09 contre 0,03 au 20/06, un rallye crypto de
juillet-août dans l'intervalle) devient secondaire : même robuste, ce réglage ne
toucherait pas la production. Reste une observation à diagnostiquer, formulée comme
hypothèse et non comme fait : une détention médiane de 0,1 jour sur les décisions du
système suggère un cycle ouvrir-puis-solder dans la même journée — le plancher de ligne
(1 000 $) est le premier suspect, à vérifier avant toute correction.
