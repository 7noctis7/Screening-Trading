# Cartographie complète du code — dossier de passation à un agent IA

> **But.** Donner à un nouvel agent une carte fiable du dépôt avant qu'il propose une
> amélioration. Ce document décrit le code et ses contrats ; il ne constitue ni une promesse
> d'alpha, ni une autorisation de trading réel. Le code, les tests et le vault restent les sources
> de vérité si ce résumé devient périmé.

## 1. Résumé exécutif

Quant Terminal est un monorepo Python/TypeScript de recherche quantitative, screening,
construction de portefeuille, paper trading et restitution Web. Son chemin nominal est :

```text
sources externes / bases locales point-in-time
  -> normalisation, contrôles et stockage
  -> facteurs, macro/régime, fondamentaux, sentiment
  -> screening et ranking
  -> stratégies et preset de portefeuille
  -> contrôles de risque et plan de rebalancement
  -> simulation ou brokers paper
  -> journal, attribution, API FastAPI et interface Next.js
```

Le projet est **paper-first**. Le seul point d'entrée autorisé pour transmettre des ordres est
`scripts/run_live.py`. La couche IA produit du texte pour l'interface ; elle n'appartient pas à la
chaîne de décision ou d'exécution. L'état déclaré par le vault est **PAPER-READY, PAS LIVE-READY** :
les résultats historiques ne justifient pas encore une affirmation d'alpha directionnel robuste.

## 2. Comment lire le dépôt sans se tromper

Ordre de lecture obligatoire :

1. `AGENTS.md` : règles de sécurité, invariants et rituel de session ;
2. `vault/00_INDEX.md` : index de la mémoire vivante ;
3. `vault/01_ARCHITECTURE.md` : architecture déclarée et état des modules ;
4. fin de `vault/04_JOURNAL.md` : derniers bugs et raisons des cicatrices du code ;
5. `vault/03_TODO.md` : dette réellement priorisée ;
6. `make brief` : état local, données disponibles et dernière session ;
7. tests du module avant son implémentation : ils expriment souvent mieux le contrat.

Ne pas considérer les chiffres de démonstration, les fallbacks ou les tests synthétiques comme des
preuves économiques. Toute calibration doit venir des bases/journaux réels ; sinon son statut est
`UNCALIBRATED`.

## 3. Architecture et frontières

### 3.1 Domaine et contrats

`packages/core/models.py` contient le vocabulaire partagé : instruments, barres OHLCV, scores de
facteurs, observations macro, régimes, signaux, ordres, positions et trades. Les objets métier sont
principalement des dataclasses typées.

`packages/core/interfaces.py` définit les ports (`Protocol`) : `DataProvider`, `Indicator`,
`Factor`, `Strategy`, `Sizer`, `RiskRule` et `Broker`. `packages/core/registry.py` fournit le registre
générique utilisé par l'architecture plugin. Le cœur n'a aucune dépendance externe obligatoire.

### 3.2 Dépendances autorisées

La direction conceptuelle est : domaine pur -> adaptateurs -> applications. Les packages métier ne
doivent pas dépendre de FastAPI, Next.js ou d'un broker concret. Les nouvelles stratégies,
indicateurs, facteurs et sources se créent comme plugins auto-enregistrés, sans ajouter de branche
au cœur.

Deux séparations sont critiques :

- `packages/intelligence` ne doit importer ni `packages.execution` ni `packages.risk` ;
- `packages/llm` n'est consommé que par l'API pour une restitution textuelle gardée.

### 3.3 Configuration et secrets

`config/` porte les univers, facteurs, features, screening, risque, exécution, macro, alertes et
mandats déclaratifs. Les paramètres sensibles et limites opérationnelles viennent de
l'environnement. `.env`, bases, caches, positions et sorties générées restent locales et ne sont
jamais commitées.

## 4. Contenu fonctionnel, package par package

### 4.1 Socle transverse

- `packages/common` : chargement de configuration/environnement, logs, event bus, planification,
  retry, mémoïsation, télémétrie, sérialisation sûre, garde point-in-time et lint du vault.
- `packages/storage` : dépôts de barres SQLite/DuckDB, couches bronze/silver/gold, feature store,
  macro store, snapshots d'univers, qualité, sauvegarde et journal SQLite.
- `packages/ontology` : résolution d'identités/symboles entre sources.
- `packages/mandate` : spécification JSON déclarative, canonicalisation, hash d'identité et harnais
  de pureté/déterminisme. Les objectifs de résultat ne doivent pas devenir des paramètres cachés.

### 4.2 Données et point-in-time

- `packages/data` : chargement/résolution de prix, registre de sources, corporate actions,
  survivorship/delistings, données crypto/FX/funding/market cap, SEC Form 4, cache Hugging Face,
  lignage, audits et SPC.
- `packages/macro` et `packages/regime` : FRED/ALFRED, FMI, surprises économiques, mapping d'impact,
  classifications de cycle/volatilité, Hurst et HMM causal. Une observation n'est utilisable qu'à
  partir de sa date de publication connue à l'époque.
- `packages/fundamentals` : providers FMP/SEC/yfinance, modèles financiers, ratios, scores
  value/quality, corporate finance et valorisation. Toute donnée historique doit respecter son
  millésime de publication.
- `packages/events` : earnings, blackouts et IPO.
- `packages/sentiment` : RSS, lexique, FinBERT optionnel, historique PIT, event-study et risk gate.

Les données locales suivent l'intention bronze -> silver -> gold. Les contrats OHLCV vérifient
notamment positivité, cohérence OHLC, timestamps, gaps et fraîcheur. Le panel de backtest doit être
aligné par **dates communes** via `packages/backtest/panel.py`, jamais par longueur minimale des
séries.

### 4.3 Signaux, screening et intelligence

- `packages/indicators` : familles trend, momentum et volatilité, registre et score technique.
- `packages/ranking` : facteurs cross-sectionnels, z-scores, pondérations et orthogonalisation.
- `packages/screening` : métriques, filtres YAML, composite, pipeline d'alpha, expectancy filter et
  journal de décision. Il produit des candidats explicables, pas des ordres.
- `packages/strategies` : plugins de conviction et blackout earnings ; les variantes doivent rester
  isolées dans un nouveau fichier plugin.
- `packages/intelligence` : classification d'énoncés, pertinence, sources, corroboration, watchlist
  et pipeline `qualifier()`. Une opinion reste une opinion ; les doublons d'origine ne créent pas
  de corroboration et les sources faibles ne confirment pas.
- `packages/profile` : profil investisseur et tilts de présentation/allocation compatibles.

### 4.4 Recherche et validation anti-faux positifs

`packages/research` contient le ledger pré-enregistré, event studies, PEAD, funding, cointegration,
microstructure (OFI/vPIN), causalité, breadth, alpha decay, attribution, coûts, sensibilité et études
adversariales. Le gate de recherche suit :

```text
hypothèse pré-enregistrée -> placebo -> Deflated Sharpe Ratio -> PBO -> sabotage/coûts
```

`packages/research/fdr.py` applique Benjamini-Hochberg lorsque plusieurs hypothèses sont criblées.
Une stratégie n'est pas promue sur son meilleur Sharpe in-sample. Il faut conserver l'intégralité
des essais dans le ledger et évaluer walk-forward/OOS avec coûts.

`packages/ml` couvre triple-barrier/meta-labeling, fractional differentiation, sample uniqueness,
purged/embargoed CV, CPCV, HPO, calibration, conformal prediction, drift, tracking d'artefacts,
promotion champion/challenger et sizing probabiliste. Le serving est découplé de l'entraînement.
Les scalers, sélections de features et calibrateurs doivent être ajustés uniquement sur le train de
chaque fold.

### 4.5 Backtest et portefeuille

- `packages/backtest/engine.py` : moteur événementiel générique.
- `packages/backtest/panel.py` : alignement temporel commun anti-fuite.
- `packages/backtest/walk_forward.py`, `walkforward.py`, `statistics.py` : OOS et statistiques.
- `packages/backtest/preset_*` : preset de production décomposé en configuration, cœur, courbes,
  diagnostics, helpers, univers rolling, poids et comptabilité.
- autres fichiers `*_backtest.py` : expériences spécialisées (breakout, conviction, crypto,
  mégacaps, ML, multi-stratégie, secteurs et pondérations).

`packages/portfolio` calcule construction/allocation (ERC, min-var, HRP, Black-Litterman), covariance
et RMT, facteurs, netting, bandes de rebalancement, vol targeting, liquidité/capacité, VaR/CVaR/EVT,
PSR/PBO, stress/scénarios, fragilité, attribution, benchmarks et revue. Ces outils ne prouvent pas à
eux seuls qu'un signal est investissable : turnover, capacité, borrow, financement, impact et
contraintes doivent être évalués ensemble.

### 4.6 Risque et exécution

`packages/risk` contient règles/vetos, limites, stops ATR, drawdown scaler, choc de corrélation et
`order_gate.py`. Ce dernier est la barrière finale :

1. il ne peut que réduire ou refuser une intention, jamais augmenter le risque ;
2. un désengagement ne doit jamais être bloqué ;
3. les limites viennent uniquement de l'environnement ;
4. chaque garde-fou publie compteur de déclenchements et effet moyen.

`packages/execution` contient :

- `rebalance_plan.py` pour convertir cibles/positions en ouvertures, allègements et liquidations ;
- `live_guards.py` pour kill-switch et lisibilité des comptes brokers ;
- coûts, impact, Almgren-Chriss, TCA, algos et routage ;
- `sim_broker.py` et adaptateurs Alpaca, Binance, Bitmart, IBKR ;
- idempotence, retry, réconciliation, journal de décision et round-trips FIFO.

La chaîne opérationnelle est strictement :

```text
snapshot/preset -> cibles -> positions brokers -> delta/rebalance_plan
  -> live guards -> order gate -> broker adapter -> résultat d'ordre
  -> réconciliation -> journal -> alertes
```

`make live` ne fait qu'un aperçu. `make live-go` vise le **paper** et exige les confirmations/clefs.
Ne jamais activer le réel, contourner `--yes`, relever une limite ou désactiver un kill-switch.

### 4.7 Restitution et applications

- `apps/api/snapshot.py` assemble le grand payload à partir des données, signaux, portefeuille,
  journal et diagnostics. C'est encore un god-object connu ; le modifier exige des tests ciblés.
- `apps/api/payloads.py` contient des builders JSON purs et testables.
- `apps/api/sections_data.py` extrait des données de sections.
- `apps/api/main.py` expose santé, métadonnées, dashboard, screener, crypto, ticker, échecs,
  portefeuille, positions, journal/trades, sentiment, fondamentaux, univers/data/thèmes, ML, live,
  conviction, investisseurs, macro, events, overlays TradingView, analytics, notes et IA gardée.
- `apps/web` est une PWA Next.js/TypeScript. Ses routes couvrent accueil/dashboard, screener,
  fiche, portefeuille/positions, risque, données/univers, macro/events/sentiment/fondamentaux,
  ML, crypto, journal/trades/live, échecs, notes, méthode, glossaire et profil.
- `packages/reporting` génère analytics, tear sheets, rapports société, MFE/MAE et notes Obsidian.
- `packages/alerts` fournit modèles, throttle, moteur, sinks et wiring event-bus.
- `packages/mcp_tradingview` fournit overlays, Pine, alertes et kill-switch TradingView.

## 5. Flux complets d'utilisation

### 5.1 Recherche d'une hypothèse

1. Écrire la thèse économique et identifier la contrepartie qui paie l'alpha.
2. Pré-enregistrer hypothèse, univers, horizon, paramètres, métrique et règle d'arrêt.
3. Obtenir uniquement les données disponibles `as_of`, incluant délistés/corporate actions.
4. Construire les features causalement ; fit des transformations dans chaque train.
5. Tester placebo, FDR, DSR, PBO, CPCV/walk-forward et stabilité par régimes.
6. Saboter avec spread, commissions, slippage, impact, borrow et financement réalistes.
7. Mesurer turnover, capacité, expositions/facteurs, queues et drawdown.
8. Journaliser aussi le résultat négatif. Promotion seulement si les gates pré-définis passent.

### 5.2 Génération du terminal

1. Les loaders résolvent bases locales ou providers configurés.
2. Les contrôles qualité et PIT filtrent les observations invalides.
3. `build_snapshot()` assemble univers, panels, métriques, régime, screen, portefeuille et sections.
4. FastAPI sert ce contrat JSON ; Next.js le rend dynamiquement ou l'export statiquement.
5. Les fallbacks doivent être étiquetés : jamais présenter du synthétique comme du réel.

### 5.3 Paper trading

1. Le preset calcule des poids cibles à partir du panel aligné et du mandat.
2. Le script lit les comptes/positions et refuse un broker illisible.
3. Il calcule uniquement le delta nécessaire, y compris les quantités de liquidation.
4. Les portes de risque réduisent/refusent les ouvertures mais laissent sortir du risque.
5. En dry-run, aucun submit ; en paper confirmé, l'adaptateur transmet avec identifiant idempotent.
6. Résultats, fills, features de décision, equity et réconciliation sont persistés.
7. Alertes et diagnostics rendent les rejets, déclenchements et divergences observables.

## 6. Commandes essentielles

| Besoin | Commande | Interprétation |
|---|---|---|
| Contexte | `make brief` | priorités, journal, santé locale |
| Tests | `make test` | gate obligatoire avant commit |
| Qualité statique | `make lint` | ruff + mypy ; dette legacy possible |
| Données | `make audit && make contracts` | audit et contrats OHLCV |
| Recherche | `make alpha-lab` / `make preset-lab` | gates d'hypothèses/preset |
| Backtest preset | `make backtest-preset` | backtest sur données locales réelles |
| Calibration | `make calibrate-preset` | sweep journalisé et DSR/PBO |
| Application | `make start` | API + front local |
| Aperçu ordres | `make live` | dry-run uniquement |
| Paper confirmé | `make live-go` | paper avec double confirmation et clés |
| Journal paper | `make verify-journal` / `make slippage` | intégrité et frictions observées |
| Mémoire | `make vault-lint` | liens, orphelins et ADR |

Les dépendances sont optionnelles par domaines dans `pyproject.toml`; Python 3.11+ est requis. Le
front possède son propre environnement Node. Les workflows GitHub couvrent CI, gitleaks, Pages,
keepalive et paper automation.

## 7. État honnête et dette connue

Ce qui est solide : contrats métier, grande couverture de tests, architecture plugin, panel aligné,
contrôles PIT, recherche adversariale, risk gate, paper-by-default, journalisation et publication des
échecs.

Ce qui ne doit pas être survendu : le DSR directionnel réel est déclaré proche de zéro ; une étude
positive sur un actif ne prouve pas une généralisation cross-sectionnelle ; le synthétique valide les
mathématiques, pas l'alpha ; « module présent » ne signifie pas toujours « câblé en production ».

Les priorités actuelles doivent être relues dans `vault/03_TODO.md`. Au moment de cette carte, elles
incluent notamment la calibration Kalman causale, le branchement du rolling universe, la correction
de la mesure `mkt`, le câblage du harnais de pureté et la consommation effective du mandat par le
preset, ainsi que l'allongement de la fenêtre du laboratoire. Ne pas créer une roadmap parallèle.

## 8. Cadre demandé au prochain agent pour proposer des améliorations

Pour chaque proposition, produire exactement :

1. **Thèse économique et microstructure** : inefficience, contrepartie, persistance et capacité.
2. **Preuve dans le dépôt** : fichiers, tests, données réelles et diagnostic observé ; distinguer fait,
   inférence et hypothèse.
3. **Formulation** : variables, équations, hypothèses, loss et contraintes.
4. **Pipeline causal** : timestamps, univers PIT, corporate actions, train/validation/test et features.
5. **Implémentation minimale** : frontière/plugin touché, compatibilité, migration et rollback.
6. **Validation pré-enregistrée** : baseline, folds purgés/embargo, DSR/PBO/FDR, régimes et critères
   d'acceptation/rejet.
7. **Frictions et capacité** : spread dynamique, commissions, slippage, impact racine carrée,
   borrow/financement, ADV et turnover.
8. **Risk controls observables** : veto, compteur de déclenchements, effet moyen, stress et limites.
9. **Red-team CRO** : leakage, survivorship, crowding, liquidité, modèle, opérationnel et black swans.
10. **Verdict** : `REJECT`, `RESEARCH_ONLY`, `PAPER_CANDIDATE` ou `UNCALIBRATED` — jamais une promesse.

### Questions d'audit prioritaires

- La fonction est-elle réellement appelée dans le flux de production ou seulement testée ?
- La date observée est-elle la date économique, la date de publication ou la date d'ingestion ?
- L'univers au temps *t* contient-il uniquement les actifs connus au temps *t* ?
- Toutes les transformations sont-elles refittées à l'intérieur de chaque fold ?
- Combien d'hypothèses ont été essayées, y compris celles non retenues ?
- Les coûts varient-ils avec volatilité, liquidité, taille et durée d'exécution ?
- Un garde-fou actif affiche-t-il zéro déclenchement ou un effet moyen nul ?
- Une panne de source/broker produit-elle un veto visible plutôt qu'un fallback silencieux ?
- Backtest, preset, snapshot et paper consomment-ils le même mandat et les mêmes conventions ?
- Peut-on reproduire le résultat avec hash git/config/données et journal des essais ?

## 9. Définition de « terminé » pour une amélioration

Une amélioration est terminée seulement si : le contrat est explicite, le test échoue avant et passe
après, les données/calibrations sont traçables, les compteurs de garde-fous sont publiés, toute la
suite passe, la documentation vivante est mise à jour et le résultat négatif éventuel est conservé.
Une hausse in-sample de Sharpe n'est pas une définition de terminé.
