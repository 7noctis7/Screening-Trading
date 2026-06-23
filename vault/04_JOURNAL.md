# 04 — JOURNAL

## Session 2026-06-23 — Sprint-0 Gouvernance (audit « Conseil Suprême ») — tout 0 €
**Fait.** Items à plus haut ratio impact/effort de la matrice d'audit, tous gratuits & CI-vérifiés.
- **#1 Gate de publication (andon)** : `scripts/check_build.py` → **échec ROUGE** du workflow Pages si
  le site est vide/tronqué/**périmé** (`meta.generated_at` ≠ aujourd'hui). Branché dans `pages.yml`
  après le build. Tue le défaut « vert mais muet ».
- **#7 Reproductibilité** : `_SNAP_VERSION` = **hash auto** du code (`snapshot.py`+`payloads.py`) → fin du
  bump manuel (risque humain éliminé). `make repro` → `out/repro.json` (git sha + config hash + version
  + seed + env). Auditabilité « niveau papier ».
- **#4 Lignage & réconciliation** : `packages/data/lineage.py` — `fingerprint()` (provenance SHA-256
  déterministe) + `reconcile()` (divergence inter-sources yf/FMP/HF, brèches > tolérance). 5 tests.
- **#13 Tests de propriété** (`hypothesis`, OSS) : invariants des noyaux maths (`_zscore` standardisé,
  ordre préservé, série constante → 0 ; `above_sma200` booléen). A **déjà débusqué** une pathologie
  d'annulation flottante (corrigée par `assume`).
- **#11 `pip-audit`** (vulns deps) ajouté au job lint CI, non-bloquant. `hypothesis`/`pip-audit` en dev.
- **#14 Manifeste d'honnêteté** : `vault/12_MANIFESTE_HONNETETE.md` (DSR≈0 assumé = le wedge).
- **526 tests verts**, ruff propre sur tout le code neuf.
**Décidé.** Reportés en sprints dédiés (risque/scope, à faire avec vérif renforcée) : **#2** démontage
du god-object `snapshot.py` (registre de sections + isolation des fautes), **#9** GARCH au sizing,
**#3** DSR en UI, **#5** SPC/CUSUM, **#8** validateur anti-hallucination LLM, **#6** facteur
prediction-markets (Kalshi/Polymarket). Le burn-down ruff/mypy (~3800) précède le passage des gates en bloquant.

## Session 2026-06-23 — Screening branché (API + page front) + mypy CI + `make screen`
**Fait.** Le moteur de screening est désormais **exposé de bout en bout**.
- **Snapshot** : `_screen_section()` (`apps/api/snapshot.py`) lance `ScreeningEngine` sur le panel de
  l'univers → section `screen` (count, universe_size, filtres, poids, rows top-50 enrichis nom/secteur/
  classe + score/reason/ret_12m/drawdown/dollar_volume). Best-effort (jamais bloquant). Smoke réel :
  **25 candidats / 929**. Bump `_SNAP_VERSION` (invalide le cache).
- **API** : `GET /api/screen` (`apps/api/main.py`) ; **dump statique** (`dump_static.py`) → `data/screen.json`
  pour la PWA ; hook `useScreen` (`lib/api.ts`).
- **Front** : page `/screener` (`apps/web/app/screener/page.tsx`) — KPIs (candidats/univers/sélectivité),
  critères appliqués, table triée par score (recherche + export CSV, EmptyState si 0). Lien nav ajouté
  (groupe Marché). Build static OK : **20 routes**.
- **CI** : `mypy packages` ajouté au job lint en **non-bloquant** (strict trop bruyant sur le legacy).
- **CLI** : `make screen` (`scripts/run_screen.py`) imprime les candidats (source de vérité = snapshot).
- **Tests** : `test_snapshot` (clé `screen` + structure) + `test_engine` (payload `_screen_section`).
  **517 verts**.

## Session 2026-06-23 — Moteur de screening (filtres YAML + scoring z-score) [P1]
**Fait.** `packages/screening/` (le stub était vide) — comble le trou P1 « screening → trading ».
- **`engine.py`** : `ScreeningEngine` = filtres durs `{metric, op, value}` (op : `> >= < <= == != between`,
  `on_missing: fail|pass`) → survivants notés par **composite z-score** (réutilise `_zscore` du ranking,
  global ou sector-neutral, facteur sans donnée ignoré). `ScreenResult` porte `passed/score/failed/
  metrics/contributions` + `reason` lisible. `from_yaml()` + `top_n` + `include_rejected`.
- **`metrics.py`** : vocabulaire unifié filtres↔scoring. Réutilise le **registre de facteurs**
  (`momentum/trend/low_vol`, et `value/quality` si fondamental chargé) + **métriques prix** internes
  (`dollar_volume`, `ret_1m/3m/6m/12m`, `dist_sma50/200`, `above_sma50/200`, `drawdown_from_high`,
  `vol_63`, `last_close`). Point-in-time (barres ≤ t). Métrique inconnue → `ValueError` franc.
- **`config/screening.yaml`** : preset (liquidité ≥5 M$, au-dessus MM200, DD > -30 %, momentum sain) +
  scoring momentum/trend/low_vol, top 25.
- **Tests** : `tests/screening/test_engine.py` (11) — filtres, between, on_missing, liquidité, ordre du
  score, top_n, métrique/op inconnus, chargement YAML. **516 passés** au total, ruff propre sur le neuf.
**Décidé.** DRY : on réutilise `_zscore`/`FactorContext`/le registre de facteurs au lieu de dupliquer.
Le screening (filtre booléen + tri) est complémentaire du ranking (tri pur pondéré régime×classe).

## Session 2026-06-23 — CI gate (pytest bloquant + ruff informatif)
**Fait.** `.github/workflows/ci.yml` : 2 jobs sur push `main` / PR / dispatch.
- **`tests`** : setup-python 3.11 + cache pip, install **lean** `.[common,data,quant,api]` + reportlab +
  scikit-learn (les tests gardent torch/vectorbt/xgboost… via `importorskip` → skip propre si absent ;
  aucun import lourd au top-level des packages), puis `pytest -q` **bloquant**. Local : **505 passés,
  4 skips, 77 s**.
- **`lint`** : `ruff check packages apps scripts` en **`continue-on-error`** (informatif). Le legacy a
  ~3857 occurrences ruff → on ratchet sans bloquer le flux ; passera bloquant après burn-down.
- `concurrency` (annule les runs superséd és) + `permissions: contents read`.
**Décidé.** mypy **différé** (strict = trop bruyant sur le legacy, gate inutilisable d'emblée). weasyprint
exclu de l'install CI (libs système cairo/pango) — seul reportlab est testé, installé directement.

## Session 2026-06-23 — Design « radical » (robuste, 0 dépendance) [PR #229]
**Fait.** (CSS-only / contenu à `Nav.tsx` → aucune régression fonctionnelle possible, build static 21/21 vert)
- **Aurora background** : ruban conique flou (`body::after`, `globals.css`), mélangé en OKLCH aux accents,
  atténué en thème clair, **coupé sous `prefers-reduced-motion`**. Rendu CSS pur → 0 WebGL, 0 dépendance,
  0 coût batterie d'un canvas (objectif « borealis » premium sans le risque).
- **Accents OKLCH** : `--accent/--accent2/--pos/--neg/--warn` en OKLCH derrière `@supports`, déclarés
  **après** les hex → fallback automatique, aucune régression possible (plus vifs sur écrans P3).
- **Typographie display** : `font-optical-sizing`, ligatures `ss01/cv01`, `text-wrap:balance`, tracking
  resserré sur les titres.
- **Nav desktop condensée** : 18 liens qui passaient à la ligne → **Accueil + 3 menus groupés**
  (Marché / Analyse / Portefeuille), pur CSS `group-hover`/`focus-within` (pas d'état JS fragile,
  accessible clavier).

**Décidé (best practice — robustesse > produit).** Les 3 items « radicaux » restants sont **écartés** car
chacun ajoute une dépendance ou un appel réseau au **build CI** → risque sur la reconstruction quotidienne
du site : WebGL aurora (OGL), View Transitions à élément partagé (`next-view-transitions` — la VT native
ne se déclenche pas sur la navigation SPA de Next), police variable (`next/font` échoue si pas de réseau au
build). L'aurora CSS couvre l'objectif visuel sans ce risque ; `pageIn` couvre déjà les transitions de page.

## Session 2026-06-23 — « Mastermind 100 » : optimisations gratuites (FinOps/perf/data/auto)
**Fait.** (toutes open-source, testées, mergées)
- **FinOps IA** : `packages/llm/local.py` (`cheap_llm` Ollama + `smart_text` routeur) → tâches simples
  sur LLM local gratuit (`QUANT_LOCAL_LLM`, ex. gemma3n:e4b/qwen2.5:3b), Claude réservé au complexe.
  Corrigé un bug : `complete()` renvoie un dict → le mémo IA n'était jamais posé.
- **RAG** : `scripts/vault_search.py` — embeddings denses Ollama (`QUANT_EMBED=ollama`,
  `nomic-embed-text`) + indexation du **code** (`--code`). Texte tronqué 4000 car. (anti-overflow 2048).
- **Perf** : hot-path prix **vectorisé** (preload 1 scan, `db_provider`), snapshot **incrémental**
  (`packages/common/memo.py`, mémoïse multi_strategy + monte_carlo), brokers Alpaca∥Bitmart en
  parallèle (ThreadPoolExecutor), analytics **DuckDB** sur Parquet (`hf_cache.momentum_ranking`),
  push HF en **Polars**.
- **Data souveraine** : cache OHLCV **Hugging Face** (`scripts/hf_cache.py`, push/pull) → CI lit le
  cache avant yfinance (fini le rate-limit). Gate **contrats** OHLCV bloquant (`contracts_check.py`,
  CI) — ne bloque que l'impossible (close≤0, high<low, vol<0), tolère trous & prix ajustés.
- **Automatisation** : miroir **Notion** (`notion_sync.py`), KPIs **Supabase** (`kpi_to_supabase.py`),
  workflow **n8n** TradingView→`/api/tv/webhook` (`integrations/n8n/`). Tous branchés au cron (best-effort).
- **Agent** : `CLAUDE.md` enrichi (nouvelles commandes), skill `/brief`, RAG code.
- **Robustesse tests** : `test_snapshot`/`test_local` rendus indépendants de l'environnement
  (clés courtier présentes, LLM local actif, univers crypto réel `-USD`).

**Décidé.** Tout est **best-effort** : chaque intégration (Ollama, HF, Notion, Supabase, n8n) se
désactive proprement si la clé/le service est absent → jamais bloquant. n8n n'a de valeur qu'avec un
tunnel public (TradingView cloud) → le webhook reste testable en local via `curl`.

## Session 2026-06-21 — Mise en ligne GRATUITE (PWA mobile) + durcissement
**Fait.**
- **Déploiement GitHub Pages + Actions** (`.github/workflows/pages.yml`) : vrai front Next.js statique
  (parité `make start`) reconstruit chaque jour ouvré + à chaque push `main`, **données réelles** dans le
  cloud (yfinance/SEC). URL : `https://7noctis7.github.io/Screening-Trading/`. Mac éteint, 0 €.
- **Pipeline statique** : `scripts/dump_static.py` (fige `/api/*` en JSON + notes HTML) →
  `scripts/build_static_site.py` (export Next.js `output:export` → `site/`). Commandes `make site` /
  `site-lite` / `watchlist`. Univers borné `config/mobile_universe.csv` (watchlist fixe + top 200).
- **Bugs CI corrigés** (verts en local, cassés en ligne) :
  - lockfile `apps/web/package-lock.json` dé-ignoré et versionné (cache npm + `npm ci`).
  - `real_macro_store` : alignement défensif valeurs↔dates (l'indice réel est plus long que le calendrier
    univers en CI) → fin de l'`IndexError` qui plantait tout le snapshot (site déployé sans données).
  - `dump_static` : `_clean()` NaN/Inf → `null` (sinon JSON invalide → pages bloquées en chargement, ex.
    Fondamentaux). `build_static_site` aborte si le dump échoue (plus de déploiement « vert mais vide »).
  - `ingest_crypto` : base normalisée `BTC-USD → BTC` (fin du `BTC-USD-USD` 404).
  - Historique CI **depuis 2015** (`--since 2015-01-01`, `QUANT_HISTORY_DAYS=4015`) au lieu de 18 mois.
- **UI/UX mobile (Apple)** : nav en **tiroir** rendu par portail (échappe au `backdrop-filter` qui
  l'écrasait), safe-area iPhone, anti-débordement horizontal, thème clair plus lisible (décor atténué),
  heatmap de corrélation scrollable. Liens notes corrigés en statique.
- **Sécurité (repo public)** : audit OK — aucun secret/clé/`.env`/`.db` traqué, historique propre, tout
  gitignoré. Username macOS neutralisé dans les chemins d'exemple.

**Décidé.** Le site **public** ne reçoit jamais les clés courtier → positions réelles **local-only**
(confidentialité). Renommage compte GitHub → l'URL Pages suit (pas de hardcode), mais ne pas renommer
pendant un run (jeton OIDC invalidé).

## Session 2026-06-20 — Notes d'analyse institutionnelles (PwC / Citadel / Apple)
**Fait.**
- **Note d'analyse par société** (HTML + PDF reportlab/weasyprint, thème clair/sombre, design Apple) :
  `packages/reporting/company_report.py` + `company_report_render.py` ; endpoint `/api/company_report`,
  page `/notes`, icône 📄 (Fondamentaux/Conviction), pré-génération nocturne `make reports`.
- **Contenu** : Portfolio Snowflake (radar 5 axes), Vernimmen (ROCE/WACC/EVA/DuPont/gearing),
  Damodaran (DCF scénarios + inversé, multiples vs secteur), 3 scores (fond/tech/ML), risk management
  (vol/VaR/CVaR/Sharpe/Sortino/stop), historique annuel + trimestriel (yfinance → SEC EDGAR 10-Q),
  actionnariat (institutionnels/insiders en %), graphes SVG (cours+MM, drawdown, CA/RN), dividende réel.
- **Gouvernance (PwC)** : audit d'intégrité + **réconciliation GAAP vs Non-GAAP** en devise de dépôt,
  **blocking alert** (>10 % CA/RN), **pénalité de surévaluation** (DCF MoS < −30 % → pilier 0 + ≤ −40 %).
- **Fiabilité** : conversion devise ADR (yfinance financialCurrency + FX gratuit), réconciliation
  alignée TTM (faux écarts dûs au change/période supprimés), EBITDA ≥ EBIT, NaN → « — ».
- Cause racine corrigée : cache yfinance v3 (nom société/devise/dividende), réordonnancement thématique.

**Décidé.** Réconciliation en devise de dépôt (intégrité) ≠ valorisation en devise du cours (marché).

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

## Session 15 — Correctifs (2026-06-16) : onglets interactifs, lxml, hygiène repo
**Fait.**
- **Bug onglets interactifs corrigé** (`build_interactive.py`). Cause racine : le helper `$()` faisait `div.innerHTML='<tr>…'` ; le navigateur **supprime les `<tr>/<td>` posés hors d'un `<table>`**, donc le rendu levait une exception après le Dashboard → onglets **Portefeuille** et **Positions vides**. Fix : chaque table construite en **UNE chaîne HTML complète** (`<table><thead>…<tbody>…</tbody></table>`) injectée d'un coup ; clics du screener **câblés après injection** via `querySelectorAll` + `data-i` (au lieu d'`onclick` sur des nœuds détachés) ; **chaque onglet enveloppé dans un `try/catch`** → une erreur ne peut plus vider les autres. Au passage : corrigé un attribut `class` **dupliqué** dans le bloc Positions (coloration P&L pos/neg cassée). `interactive.html` régénéré + ouvert : les 3 onglets s'affichent.
- **Dépendance manquante** : `lxml` ajouté à l'extra `data` de `pyproject.toml` (requis par `pd.read_html` dans `wikipedia_source.py`). Tests `test_wikipedia_parser.py` rendus robustes : `pytest.importorskip("pandas"/"lxml")` → **skip propre** si absent au lieu d'échouer.
- **Hygiène repo** : `.gitignore` (re)créé (absent du dépôt malgré la note S0 — perdu aux uploads) couvrant `__pycache__`, `.env`, artefacts data, `.DS_Store` ; `.DS_Store` déjà suivis retirés (`git rm --cached apps/.DS_Store apps/web/.DS_Store`).
- **154 tests verts** (aucune régression).

**Décidé.** ADR-0022 (DOM : tables injectées en une chaîne complète + rendu d'onglet isolé par try/catch).
