# 04 — JOURNAL

## Session 0 — Fondation
**Fait.**
- Posé le monorepo (section 3 du prompt maître) : `apps/`, `packages/`, `config/`, `tests/`, `vault/`.
- `packages/core` (domaine pur, zéro dépendance) : `models.py` (Instrument, Bar, Signal, Order,
  Position, RegimeState, FactorScore, TradeRecord + enums), `interfaces.py` (DataProvider, Indicator,
  Factor, Strategy, Sizer, RiskRule, Broker, RiskDecision), `registry.py` (plugins auto-enregistrés).
- `packages/common` : `config.py` (YAML), `logging.py` (JSON structuré), `event_bus.py` (pub/sub + topics).
- Configs YAML d'exemple : `universe`, `risk`, `factors`, `strategies/ma_crossover`.
- Tests : `test_registry` (validation archi plugin), `test_models`, `test_event_bus`.
- `pyproject.toml` (uv/ruff/mypy/pytest, deps par groupe), `.gitignore`, `.env.example`, `README`.
- Vault initialisé : INDEX, ARCHITECTURE (schéma vivant + 2 diagrammes Mermaid), DECISIONS (ADR-0001),
  TODO (roadmap P0/P1/P2), + stubs 05→12.

**Décidé.** ADR-0001 (stack & archi de fondation).

**Prochaine priorité.** P0 : CI (ruff/mypy/pytest) → Storage (bronze/silver/gold + Alembic) →
premier `DataProvider` (yfinance) avec normalisation OHLCV UTC + cache.

**Note.** Aucune logique de trading réelle écrite (garde-fou respecté). Attente du feu vert
pour entamer l'implémentation des modules métier.

## Session 1 — Tranche verticale runnable (data → backtest → métriques)
**Fait.**
- **Data** : `DataProvider` synthétique (GBM seedé, offline, reproductible) + yfinance (réel), auto-enregistrés.
- **Indicateurs** (numpy, anti-look-ahead testé) : SMA, EMA, MACD, **régression log-linéaire z-score**, RSI, ROC, ATR, largeur Bollinger.
- **Régime** : classifieur rule-based v1 (tendance vs SMA + pente, vol réalisée → cycle + risk-on/off), `extras` prêt pour FRED/surprises.
- **Stratégies** plugins : `ma_crossover` (trend), `rsi_reversion` (mean-reversion), stop/target ATR-based.
- **Sizing** : `fixed_fractional`, `vol_target` (Kelly-cap). **Risk engine** : règles veto (R:R, max positions, expo/actif) + **kill-switch drawdown quotidien**.
- **Exécution** : `CostModel` (frais+slippage) + `SimBroker` paper (sert backtest ET live → parité).
- **Backtest** : moteur event-driven multi-instruments, broker partagé, gestion stop/target, **journal avec snapshot features + R-multiple + MFE/MAE**.
- **Métriques** : Sharpe/Sortino/Calmar/MaxDD/profit factor/win rate/expectancy.
- **Démo** `scripts/demo_backtest.py` : tourne offline → résultat **honnête -1,1%** (trend sur quasi-random après coûts = attendu, pas d'alpha fabriqué). R-multiple -1.0 sur stops / +2.49 sur targets : accounting validé.
- **21 tests** verts (indicateurs/sizing/risque/moteur + archi).

**Décidé.** ADR-0002 (indicateurs groupés par famille) · ADR-0003 (broker simulé partagé backtest/live pour la parité) · ADR-0004 (sizer plafonné à la limite d'expo, risk engine = backstop dur).

**Découverte utile.** Sizer vol-target (20% capital) vs cap expo/actif (10%) → veto systématique : preuve que le risque a bien le dernier mot. Corrigé en calant le plafond du sizer sur la limite.

**Correctif clé (S1).** Déterminisme : remplacé `hash()` builtin (randomisé/process) par `hashlib` dans le provider synthétique → backtests reproductibles (ADR-0005, test dédié).

**Prochaine priorité.** P0 : Storage bronze/silver/gold (DuckDB+Parquet) + repository de persistance du journal + contrats pandera. Puis P1 : screening/ranking multi-facteur réel + walk-forward + deflated Sharpe.

## Session 2 — Storage (medallion) + univers + qualité + réponses design
**Fait.**
- **Univers** : loader `config/universe.yaml` → `Instrument`, séparation **tradables (4)** / **benchmarks (3)**.
- **Storage** : `SqliteBarsRepository` (stdlib) — bronze/silver, clé `(symbol,timeframe,ts)`, **UPSERT idempotent**, `last_ts()` pour l'incrémental, multi-timeframe natif.
- **Qualité** : `validate_ohlcv` (prix>0, cohérence OHLC, ts uniques/croissants, trous, fraîcheur) → `enforce` **bloque** le pipeline si KO. Pandas pur (pandera brranchable plus tard).
- **Démo** recâblée sur l'**univers réel** via pipeline medallion (provider→bronze→validation→silver→backtest). Corrigé l'incohérence : la démo codait 5 symboles ≠ univers (7 déclarés).
- **+10 tests** (33 verts). Reproductible (+0.2% stable).

**Décidé.** ADR-0006 (SQLite now / DuckDB cible + timeframe daily canonique) · ADR-0007 (pas de LLM dans le chemin chaud).

**Réponses design consignées** (questions utilisateur) : voir 08_DATA_MODEL (politique timeframe/cadence) et ADR-0007 (agents IA).

**Prochaine priorité.** Gold layer + feature store (indicateurs/facteurs stockés) → screening/ranking multi-facteur réel → walk-forward + deflated Sharpe. Brancher DuckDB+Parquet (même interface) quand volumes réels.

## Session 3 — Univers multi-marchés (source-driven) + ranking multi-facteur
**Fait.**
- **Moteur d'univers** : `UniverseBuilder` + sources plugins — `static` (seeds offline), `wikipedia`, `nasdaq_trader` (listings US complets), `coingecko`. Dédoublonnage + **snapshot daté** (point-in-time, anti-survivorship). `UniverseRepository` (SQLite).
- **Seeds exacts** : forex(20), commodities(20), indices(20), ETF(101 par secteur/industrie/géo), crypto(100), CAC40(40), AEX(24). Sources réseau pour SP500/Nasdaq100/SBF120/FTSE100/FTSE MIB/Nikkei/KOSPI/CSI300 + NYSE/Nasdaq complets.
- **Offline = 325 instruments** ; en ligne = milliers. Démo recâblée sur le builder (échantillon de 12 pour la vitesse) ; corrigé l'incohérence univers↔démo.
- **Ranking multi-facteur** (Module 4) : facteurs momentum/trend/low-vol (cross-sectional z-score), pondérations **régime × classe**, applicabilité (forex/crypto sans value/quality), **top N explicable** (contribution par facteur + raison).
- `scripts/build_universe.py` (--network), +11 tests (44 verts).

**Décidé.** ADR-0008 (univers source-driven + snapshots datés, jamais de tickers en dur).

**Réponse à la demande univers** : les ~milliers de titres viennent des sources réseau à l'exécution chez l'utilisateur — pas codés à la main (anti-hallucination/péremption).

**Prochaine priorité.** Fondamental & valorisation (Module 6 : ratios Vernimmen + DCF/multiples Damodaran → facteurs value/quality) → couche gold/feature store (stocker indicateurs+facteurs) → walk-forward + deflated Sharpe. Puis brancher yfinance/FMP réel + DuckDB.

## Session 4 — Univers mensuel + Russell + dédoublonnage + fondamental
**Fait.**
- **Mensuel** : `rebuild_cadence_days: 30`, `build_universe.py` cadence-aware (`--force`), `scripts/scheduler.py` (APScheduler, cron 1er du mois) + helper `due_for_rebuild` testé. → réponse : OUI, l'univers s'update une fois/mois (avant : non, manuel).
- **Russell 1000/3000** : source `ishares_holdings` (IWB/IWV), parser préambule CSV + filtre Equity + dot_to_dash.
- **Dédoublonnage par symbole** (priorité = ordre des sources) → tous les doublons inter-sources retirés ; `duplicates_removed` rapporté. Vérifié (seed ETF ×2 → 101 retirés).
- **Module fondamental** (Module 6) : ratios Vernimmen (ROE/ROIC/marges/net debt-EBITDA/FCF), valorisation Damodaran (PER/EV-EBITDA/P-B + **DCF FCFF + marge de sécurité**), provider synthétique déterministe (réel FMP/yfinance via même interface).
- **Facteurs value/quality** branchés dans le ranking (refactor à **contexte** : technique + fondamental cohabitent ; z-score **sector-neutral** pour value/quality ; facteur sans donnée = retiré proprement).
- +13 tests (57 verts).

**Décidé.** ADR-0009 (cadence mensuelle) · ADR-0010 (dedup par symbole) · ADR-0011 (Russell via iShares).

**Prochaine priorité.** Couche **gold/feature store** (stocker indicateurs+facteurs+fondamentaux datés) → **walk-forward + deflated Sharpe** → brancher providers réels (yfinance/FMP) + DuckDB. Puis screening top-down macro (FRED/ALFRED point-in-time).

## Session 5 — Couche gold (feature store) + walk-forward + deflated Sharpe
**Fait.**
- **Feature store (GOLD)** : `FeatureStore` SQLite + `materialize_indicators` (config `features.yaml`) → indicateurs point-in-time matérialisés depuis silver. **Anti training/serving skew** (test : store == recalcul). NaN de warm-up non stockés.
- **Statistiques de robustesse** : PSR + **Deflated Sharpe** (Bailey/López de Prado), stdlib (`NormalDist`). Corrige taille d'échantillon, non-normalité ET multiple testing.
- **Walk-forward** : `WalkForwardRunner` (fenêtres roulantes train→test, warm-up, sélection in-sample, éval OOS), DSR sur nb total d'essais. `scripts/demo_walkforward.py`.
- Démo : OOS +7.8% / Sharpe 0.46 / PSR 0.90 mais **DSR=0.00** sur 64 essais → "NON significatif" (garde-fou anti-surapprentissage qui marche).
- +10 tests (67 verts).

**Décidé.** ADR-0012 (feature store anti-skew) · ADR-0013 (walk-forward + deflated Sharpe).

**Prochaine priorité.** Brancher providers RÉELS (yfinance/FMP) + DuckDB+Parquet (même interfaces) pour quitter le synthétique → premiers backtests sur vraies données + walk-forward. Puis macro/régime point-in-time (FRED/ALFRED) et exécution paper Alpaca.

## Session 6 — Providers réels (yfinance/FMP) + DuckDB (drop-in)
**Fait.**
- **Wrappers** composables (testés) : `FallbackProvider`, `CachingProvider` (+persistance silver), `RateLimiter`/`RateLimitedProvider` (horloge injectable).
- **yfinance** : normalisation `df_to_bars` pure/testée (UTC, multi-index aplati) ; fetch réseau isolé.
- **FMP** : `FMPFundamentalsProvider` + `build_financials` (mapping JSON→Financials, testé fixture). Branche les vrais fondamentaux dans value/quality.
- **DuckDB** : `DuckDBBarsRepository` drop-in (même interface) + `export_parquet` ; `make_bars_repository(backend)` (sqlite|duckdb). Test DuckDB skippé proprement hors-ligne.
- `config/data_sources.yaml` (ordre fallback, quotas, provider fondamental). `scripts/verify_real_data.py` (smoke test en ligne).
- +11 tests (78 verts).

**Décidé.** ADR-0014 (providers réels via wrappers + backend pluggable).

**Note offline.** duckdb/yfinance/pyarrow absents ici → code écrit pour ton env ; logique 100% testée via fixtures/mocks. Lance `scripts/verify_real_data.py` avec réseau.

**Prochaine priorité (étape 2).** Macro & régime **point-in-time** : ingestion FRED/ALFRED (vintages), surprises éco (réalisé vs consensus), cartographie macro→actifs, classification du cycle → `RegimeState` quotidien enrichi. Puis (étape 3) exécution paper Alpaca.

## Session 7 — Macro & régime point-in-time (FRED/ALFRED, surprises, cartographie)
**Fait.**
- **MacroStore** (vintages) + `as_of` point-in-time : respecte délai de publication ET révisions (logique ALFRED). Testé sur scénario CPI publié+révisé.
- **FredProvider** (réel) + parser `parse_observations` (testé fixture) ; **synthetic_macro** (offline, lag de publication).
- **Surprises éco** (`surprise_index`) : réalisé vs consensus, par thème (inflation/croissance/emploi), point-in-time.
- **Cartographie macro→actifs** (`config/macro_impact.yaml` + `MacroImpactMap`) : multiplicateur d'exposition (risk_mode × cycle), inclinaisons de facteurs et de classes selon surprises.
- **MacroRegimeClassifier** (nowcasting) : courbe 2s10s + ISM/PMI + chômage + VIX → cycle + risk-on/off, point-in-time.
- Modèles domaine : `MacroObservation`, `EconomicRelease`. `config/macro.yaml`. `scripts/demo_macro_regime.py`.
- +14 tests (92 verts).

**Décidé.** ADR-0015 (macro point-in-time + cartographie).

**Prochaine priorité (étape 3).** Exécution **paper Alpaca** : `AlpacaBroker` (implémente l'interface Broker, paper natif), réconciliation broker↔DB, retries idempotents — puis boucle live paper (kill-switch visible). Toujours zéro réel sans feu vert.

## Session 8 — Exécution paper Alpaca + moteur live (parité backtest↔live)
**Fait.**
- **AlpacaBroker** (interface Broker, paper natif) + mappers purs testés ; réseau isolé.
- **LiveTradingEngine** : réutilise Strategy/Sizer/RiskEngine/Broker/Journal du backtest, en streaming (step par barre) → **parité**. Kill-switch visible à chaque pas.
- **Retries idempotents** (`submit_with_retries` + client_id ; SimBroker rendu idempotent → 2 submits même id = 1 fill). Backoff exponentiel, sleep injectable.
- **Réconciliation** broker↔interne (`reconcile`) + alerte event-bus sur divergence.
- `config/execution.yaml`. Démos : `demo_paper_loop.py` (offline SimBroker), `verify_alpaca.py` (ton env, paper).
- +13 tests (104 verts).

**Décidé.** ADR-0016 (paper Alpaca + parité + idempotence/réconciliation).

**Note offline.** alpaca-py absent ici → AlpacaBroker écrit pour ton env (mappers testés) ; toute la logique (live engine, idempotence, retries, réconciliation) testée via SimBroker. Lance `verify_alpaca.py` avec clés paper.

**Séquence des 3 étapes proposées TERMINÉE** (providers réels → macro/régime → paper). Reste roadmap : ML (triple-barrier, purged CV, MLflow), alertes multi-canal, excellence op (observabilité/CI-CD/tear sheets PDF), **front-end** Next.js, et live réel (sur feu vert).

## Session 9 — Module ML (triple-barrier, CV purgée, gouvernance)
**Fait.**
- **Labeling** : triple-barrière (profit/stop/temps) + meta-labeling + vol EWM (`packages/ml/labeling.py`).
- **CV PURGÉE & embargo** (`PurgedKFold`) : retire les labels chevauchant le test → OOS honnête.
- **Features** : différenciation fractionnaire + `FeatureBuilder` point-in-time (technique gold + macro `as_of`).
- **Modèles** : `LogitModel` (numpy pur, baseline testable) + `SklearnModel`/xgboost ; `make_model`.
- **Évaluation** : accuracy/précision/rappel + `purged_cv_score`.
- **Gouvernance** : `champion_challenger` (marge + barrière de risque) + `ModelRegistry`.
- Démo offline : OOS ~50% sur synthétique (anti-surapprentissage confirmé). +16 tests (120 verts).

**Décidé.** ADR-0017 (ML López de Prado).

**Reste roadmap.** Alertes multi-canal (Telegram/Discord) · excellence op (observabilité, drift, audit, CI/CD, tear sheets PDF) · **front-end Next.js** (dashboard/screener/portefeuille/positions) · live réel (sur feu vert).

## Session 10 — API FastAPI (contrat testé) + front Next.js + aperçu HTML
**Fait.**
- **Builders de payloads** purs et testés (`apps/api/payloads.py`) : régime, equity, screener, composition (totaux/P&L/exposition brute-nette), métriques, comparaison benchmarks rebasés, sérialisation trades JSON-safe.
- **snapshot.py** : état complet (dashboard/screener/portfolio/trades) depuis un run offline — **100% JSON-sérialisable** (vérifié).
- **FastAPI** (`apps/api/main.py`) : routes /health, /api/{dashboard,screener,portfolio,positions,trades} + CORS (ton env).
- **Front Next.js** : tokens (`lib/tokens.ts`) + tailwind + client TanStack Query (`lib/api.ts`) + Dashboard (page + MetricCard + RegimeBanner) + README.
- **Aperçu HTML statique** (`apps/web/preview/dashboard.html`) rendu depuis les vraies données (dark, SVG equity vs S&P 500, screener, P&L) — ouvrable sans build.
- `11_DESIGN_SYSTEM.md` rempli (tokens concrets). +7 tests (127 verts).

**Décidé.** ADR-0018 (API contrat testé + front consommateur).

**Note offline.** fastapi/uvicorn absents + pas de `npm install` (réseau) → app FastAPI et front écrits pour ton env ; toute la logique d'assemblage (payloads, snapshot) testée. Lance `uvicorn apps.api.main:app` puis `npm run dev`.

**Reste roadmap.** Alertes multi-canal · excellence op (observabilité/drift/audit/CI-CD/tear sheets PDF) · écrans front restants (portefeuille/analyse, positions, backtest) · live réel (feu vert).

## Session 11 — Analyse de portefeuille (relatif, risque, corrélation, revue) + écrans
**Fait.**
- **Mesures relatives** (`benchmark.py`) : beta, alpha Jensen, tracking error, information ratio, R², up/down capture.
- **VaR/CVaR** (`risk_metrics.py`) historique + paramétrique (Jorion).
- **Corrélation + clustering** (`correlation.py`) single-linkage → anti fausse-diversification.
- **Attribution** du P&L (`attribution.py`) par stratégie/actif/classe.
- **Stress test + Monte Carlo** (`stress.py`) : choc via beta, proba de ruine, worst DD, VaR de trajectoire.
- **Revue experte** (`review.py`) CFA/FRM/CPA/CAIA : ancrée sur les métriques (zéro chiffre inventé) + score de santé + recommandations priorisées.
- Exposé dans l'API (`/api/portfolio` → `analysis`) et le snapshot (JSON-sérialisable).
- **Front** : pages `portfolio` + `positions` (Next.js) + composants ExpertReview / CorrelationHeatmap. **Aperçus HTML** dashboard + **portfolio** (heatmap, revue, risque) rendus depuis les vraies données.
- +10 tests (137 verts).

**Décidé.** ADR-0019 (moteur analytique portefeuille).

**Reste roadmap.** Écran backtest/tear sheets · WebSocket live · alertes multi-canal · excellence op (observabilité/drift/audit/CI-CD/tear sheets PDF) · live réel (feu vert).

## Session 12 — Alertes & notifications multi-canal
**Fait.**
- **Moteur** (`AlertEngine`) : routage par sévérité (INFO/WARNING/CRITICAL), historique pour audit, tolérant aux canaux en échec.
- **Sinks** : InMemory/Console (testables) + Telegram/Discord (réseau, `format_message` pur/testé).
- **Throttle** anti-spam (TTL + dedup_key, horloge injectable).
- **Handlers** (1/type) abonnés à l'event bus : régime, kill-switch, rejet risque, qualité données, fill, divergence broker↔DB (`register_on_bus`).
- `config/alerts.yaml`, `scripts/demo_alerts.py`. +9 tests (146 verts).

**Décidé.** ADR-0020 (alertes multi-canal).

**Reste roadmap.** Excellence op (observabilité/drift/audit/CI-CD/tear sheets PDF) · écran backtest + WebSocket live · live réel (feu vert).

## Session 13 — Excellence opérationnelle
**Fait.**
- **Drift ML** (`ml/drift.py`) : PSI par feature + statut + drapeau, branché aux alertes (drift → réentraînement).
- **Audit trail** (`common/audit.py`) : append-only, rejouable, contexte JSON (features/régime/modèle).
- **Télémétrie** (`common/telemetry.py`) : compteurs/gauges/timers → snapshot santé.
- **Backup/restore** SQLite (`storage/backup.py`), testés (données préservées).
- **Tear sheets** (`reporting/tearsheet.py`) : HTML autonome + **PDF reportlab**.
- `scripts/demo_ops.py`. +8 tests (154 verts).

**Décidé.** ADR-0021 (excellence opérationnelle).

**Reste roadmap.** Écran backtest + WebSocket live · live réel (feu vert) · allocation PyPortfolioOpt · international macro (FMI/OCDE).

## Session 14 — Front interactif (hover/tooltips) + procédure de test
**Fait.**
- **Aperçu interactif autonome** (`apps/web/preview/build_interactive.py` → `interactive.html`) : onglets, courbe d'equity avec crosshair+tooltip au survol, compteurs animés, screener cliquable (barres de facteurs), heatmap de corrélation au survol. Un seul fichier, aucune install.
- **EquityChart** Recharts (tooltip/crosshair) branché au dashboard Next.js → vrai site interactif.
- `scripts/check_all.sh` (tests+démos+aperçus) et `TESTING.md` (procédure de test pas-à-pas).

**Note.** Les aperçus *statiques* (dashboard/portfolio.html) restent non interactifs (SVG serveur) ; `interactive.html` et le front Next.js portent l'interactivité.
