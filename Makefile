.PHONY: install setup test lint demos start stop api api-dev api-lan web preview interactive ingest daily cron cron-install cron-uninstall tearsheet train backtest-ml backtest-weighting backtest-earnings backtest-breakout backtest-sentiment backtest-preset backtest-megacap index-core index-core-stress index-core-regime crypto-core ledger-sweep ingest-crypto ingest-mktcap preset-report calibrate-preset screen repro kill-check log-alpha sync-alphas event-study event-study-smid backtest-pead-smid funding-study risk-check sensitivity paper-watch vault-lint crypto-onchain screen-niche list-db live live-go clean mcp-tv mcp-selftest mcp-overlays vault-sync audit ingest-delisted reports watchlist site site-lite analytics brief vault-search hf-push hf-pull notion-sync contracts supabase-kpis
# PYTHON : utilise AUTOMATIQUEMENT le venv s'il existe (.venv/bin/python), sinon python3 système.
# Évite le piège « No module named numpy » quand le venv n'est pas activé. Surchargeable.
TICKER ?= AAPL
PYTHON ?= $(shell [ -x .venv/bin/python ] && echo .venv/bin/python || echo python3)
install:          ## installe les dépendances (uv)
	uv venv && uv pip install -e ".[dev,data,quant,api,ml]"
setup:            ## installation locale guidée (venv, détection YAHOO.db, build, cron) — 1 commande
	bash scripts/setup_local.sh
test:             ## lance la suite de tests
	$(PYTHON) -m pytest -q
lint:             ## ruff + mypy
	ruff check packages apps && mypy packages
demos:            ## exécute les démos offline
	$(PYTHON) scripts/demo_backtest.py && $(PYTHON) scripts/demo_walkforward.py && \
	$(PYTHON) scripts/demo_macro_regime.py && $(PYTHON) scripts/demo_ml.py && \
	$(PYTHON) scripts/demo_paper_loop.py && $(PYTHON) scripts/demo_alerts.py && $(PYTHON) scripts/demo_ops.py
preview:          ## régénère les aperçus HTML du dashboard/portefeuille
	$(PYTHON) apps/web/preview/build_preview.py
start:            ## TOUT EN UNE COMMANDE : maj code + kill vieux process + API (fond) + site
	bash scripts/start.sh
stop:             ## arrête l'API et le site (uvicorn + next dev)
	@pkill -f "uvicorn apps.api.main" 2>/dev/null; lsof -ti:8000 2>/dev/null | xargs kill -9 2>/dev/null; lsof -ti:3000 2>/dev/null | xargs kill -9 2>/dev/null; echo "arrêté"
api:              ## lance l'API FastAPI (localhost) — STABLE, sans reload (évite l'OOM pendant make daily)
	$(PYTHON) -m uvicorn apps.api.main:app
api-dev:          ## API avec reload du CODE seulement (apps/packages) — ne surveille PAS data/ (dev)
	$(PYTHON) -m uvicorn apps.api.main:app --reload --reload-dir apps --reload-dir packages
api-lan:          ## lance l'API accessible depuis le téléphone (même Wi-Fi) → http://IP_DU_MAC:8000
	$(PYTHON) -m uvicorn apps.api.main:app --host 0.0.0.0 --port 8000
web:              ## lance le front Next.js
	cd apps/web && npm install && npm run dev
interactive:      ## génère la preview autonome (apps/web/preview/interactive.html)
	$(PYTHON) apps/web/preview/build_interactive.py
ingest:           ## backfill des prix réels (yfinance) → data/market.db
	$(PYTHON) scripts/ingest_prices.py --since 2015-01-01
daily:            ## mise à jour incrémentale quotidienne des prix réels
	$(PYTHON) scripts/ingest_prices.py --daily
cron:             ## maj quotidienne complète (prix + terminal) — à mettre en crontab/launchd
	bash scripts/cron_daily.sh
cron-install:     ## ACTIVE la maj quotidienne auto (macOS launchd / Linux crontab) — 1 commande
	bash scripts/install_cron.sh
cron-uninstall:   ## désactive la maj quotidienne automatique
	bash scripts/install_cron.sh --uninstall
tearsheet:        ## exporte un tear sheet de performance (out/tearsheet.html + .pdf si reportlab)
	$(PYTHON) scripts/export_tearsheet.py
train:            ## entraîne le modèle ML hors-ligne → models/ (serving découplé, ticket #2)
	$(PYTHON) scripts/train_model.py
backtest-ml:      ## backtest ML walk-forward point-in-time (conviction+ML vs technique vs bench)
	$(PYTHON) scripts/backtest_ml.py
backtest-weighting:  ## compare equipondere/inverse-vol/min-var/risk-parity (net de frais)
	$(PYTHON) scripts/backtest_weighting.py
backtest-earnings:   ## backtest PEAD (earnings drift, dates via yfinance)
	$(PYTHON) scripts/backtest_earnings.py
backtest-breakout:   ## backtest cassures Donchian + measure rule (Bulkowski)
	$(PYTHON) scripts/backtest_breakout.py
backtest-sentiment:  ## event-study : le signal sentiment a-t-il un edge ? (data/news.csv requis)
	$(PYTHON) scripts/backtest_sentiment.py
backtest-preset:     ## backtest walk-forward du preset best-practice + overlay vol gérée (tes données)
	$(PYTHON) scripts/backtest_preset.py
backtest-megacap:    ## top-N méga-caps (rotation classement) vs S&P/Nasdaq réels
	$(PYTHON) scripts/backtest_megacap.py
index-core:          ## sweep cœur(s) + preset (QQQ / top-10 méga-caps) sur la vraie data
	$(PYTHON) scripts/index_core_sweep.py $(ARGS)
index-core-stress:   ## stress-test BEAR : perte du portefeuille par ratio QQQ pendant les krachs
	$(PYTHON) scripts/index_core_stress.py $(ARGS)
index-core-regime:   ## allocation adaptative bull/range/bear (détection MM200 S&P) vs fixe
	$(PYTHON) scripts/index_core_regime.py $(ARGS)
crypto-core:         ## cœur crypto BTC + panier majeures (équivalent QQQ pour Bitmart)
	$(PYTHON) scripts/crypto_core_sweep.py $(ARGS)
ledger-sweep:        ## perf RÉALISTE (journal discret) par % QQQ × DD-target × rebalancement
	$(PYTHON) scripts/ledger_sweep.py $(ARGS)
ingest-crypto:       ## ingère les prix des top-N cryptos (yfinance) → data/crypto.db (prix RÉELS)
	$(PYTHON) scripts/ingest_crypto.py $(ARGS)
ingest-mktcap:       ## ingère les market caps (yfinance) → data/market_caps.json (cœur cap-weighted)
	$(PYTHON) scripts/ingest_market_cap.py $(ARGS)
preset-report:       ## rapport HTML autonome du backtest preset (courbes + drawdowns) → out/preset_report.html
	$(PYTHON) scripts/export_preset_report.py
calibrate-preset:    ## calibre le preset (DD × top-K × bande) par Sharpe déflaté (anti-overfit)
	$(PYTHON) scripts/calibrate_preset.py
screen:              ## screener à filtres (config/screening.yaml) → candidats triés par z-score
	$(PYTHON) scripts/run_screen.py
repro:               ## manifeste de reproductibilité (git sha + config/data hash + env) → out/repro.json
	$(PYTHON) scripts/repro_manifest.py
kill-check:          ## kill-switch INTRADAY : drawdown réel vs seuil (cron N×/j, aucun ordre)
	$(PYTHON) scripts/kill_switch_check.py
log-alpha:           ## logue un essai d'hypothèse d'alpha (ledger anti p-hacking) — voir ARGS
	$(PYTHON) scripts/log_hypothesis.py $(ARGS)
sync-alphas:         ## propage le ledger vers le frontmatter des notes vault/08_Alphas/
	$(PYTHON) scripts/sync_alpha_notes.py
event-study:         ## event-study 1 ticker (TICKER=AAPL) ou PANIER (TICKERS="AAPL,MSFT,NVDA")
	$(PYTHON) scripts/event_study_cli.py --ticker $(TICKER) $(if $(TICKERS),--tickers $(TICKERS)) $(ARGS)
SMID ?= CROX,ELF,CELH,RMBS,POWI,AAON,SPSC,ASO,BOOT,CALM,SHAK,FN
event-study-smid:    ## PEAD sur small/mid-caps (moins couvertes → dérive candidate)
	$(PYTHON) scripts/event_study_cli.py --tickers "$(SMID)" --source earnings $(ARGS)
backtest-pead-smid:  ## backtest PEAD small/mid NET de coûts + gate DSR/PBO (le vrai juge)
	$(PYTHON) scripts/backtest_pead_smid.py $(ARGS)
funding-study:       ## event-study funding crypto (reversion) + placebo — gate avant backtest
	$(PYTHON) scripts/funding_study_cli.py $(ARGS)
risk-check:          ## exposition brute recommandée (drawdown taper × vol prévue) — edge prouvé
	$(PYTHON) scripts/risk_check_cli.py $(ARGS)
sensitivity:         ## sensibilité des seuils (screening Jaccard + régime) — anti sur-optim
	$(PYTHON) scripts/sensitivity_cli.py $(ARGS)
paper-watch:         ## watchdog dérive paper vs backtest (cron nocturne) — exit≠0 si dérive
	$(PYTHON) scripts/paper_watch.py $(ARGS)
vault-lint:          ## intégrité du vault (liens morts, orphelins, ADR en double)
	$(PYTHON) scripts/vault_lint.py $(ARGS)
crypto-onchain:      ## fondamentaux on-chain (CoinGecko + DefiLlama, sans clé) — table 8 cryptos
	$(PYTHON) scripts/crypto_onchain_cli.py $(ARGS)
screen-niche:        ## audit d'exploitabilité d'un univers/niche (score 0-100) avant de s'engager
	$(PYTHON) scripts/screen_niche.py
list-db:             ## liste ce que contient YAHOO.db (classes/secteurs) → pour bâtir une vraie niche
	$(PYTHON) scripts/build_niche.py
live:             ## APERÇU des ordres à répliquer (dry-run, aucun ordre envoyé)
	$(PYTHON) scripts/run_live.py --equity 10000
live-go:          ## EXÉCUTE en paper (Alpaca paper + Bitmart) — clés API requises
	$(PYTHON) scripts/run_live.py --live --yes
mcp-tv:           ## lance le serveur MCP TradingView (overlays, Pine, alertes) — stdio, en parallèle de l'API/front
	$(PYTHON) -m packages.mcp_tradingview.server
mcp-selftest:     ## auto-vérif des outils MCP en mémoire (sans handshake) — liste + génère un Pine
	$(PYTHON) -c "from packages.mcp_tradingview import server as s; import json; \
print('outils:', [t['name'] for t in s.list_tools()]); \
print('pine ok:', s.call_tool('generate_pine_script', {'strategy_name':'selftest'})['pine'][:14])"
mcp-overlays:     ## calcule les cônes VaR/EVT (prix réels) + blackouts et les pousse au chart (API démarrée requise)
	$(PYTHON) scripts/mcp_populate_overlays.py
vault-sync:       ## régénère le coffre Obsidian (journal du jour, attribution, post-mortems) depuis YAHOO.db
	$(PYTHON) -m packages.reporting.obsidian
audit:            ## audit PwC des bases de prix (complétude/exactitude/point-in-time) — make audit ARGS=--strict
	$(PYTHON) scripts/data_audit.py $(ARGS)
ingest-delisted:  ## détecte les titres délistés (barres trop anciennes) → data/delisted.csv (anti-biais du survivant)
	$(PYTHON) scripts/ingest_delisted.py $(ARGS)
reports:          ## pré-génère les notes d'analyse (top-conviction + positions) → out/notes/AAAA-MM-JJ
	$(PYTHON) scripts/generate_reports.py $(ARGS)
watchlist:        ## top 200 par note + watchlist fixe → config/mobile_universe.csv + rapport Obsidian (borne la PWA en ligne)
	$(PYTHON) scripts/build_watchlist.py $(ARGS)
site:             ## TOUT-EN-UN MOBILE (front COMPLET Next.js) : watchlist + données + export + serveur (http://localhost:8080)
	bash scripts/start_full.sh
site-lite:        ## variante LÉGÈRE sans Node (terminal autonome interactive.html) + serveur local
	bash scripts/start_mobile.sh
analytics:        ## rapport de perf QuantStats (Sortino/Calmar/Alpha-Beta vs QQQ) → vault/Performance_Report.md
	$(PYTHON) scripts/perf_report.py
brief:            ## brief unifié (priorités + journal + changements + audit) → stdout (ARGS=--write → vault/_BRIEF.md)
	$(PYTHON) scripts/daily_brief.py $(ARGS)
vault-search:     ## recherche sémantique locale du vault — make vault-search Q="ta question" (TF-IDF ; QUANT_EMBED=ollama)
	$(PYTHON) scripts/vault_search.py search "$(Q)" -k $(or $(K),5)
hf-push:          ## pousse le cache OHLCV (market+crypto) vers le dataset HuggingFace (HF_TOKEN requis)
	$(PYTHON) scripts/hf_cache.py push $(ARGS)
hf-pull:          ## reconstruit data/*.db depuis le cache HuggingFace public (sans token)
	$(PYTHON) scripts/hf_cache.py pull $(ARGS)
notion-sync:      ## miroir Obsidian → Notion (NOTION_TOKEN + NOTION_PARENT requis) — ARGS pour cibler des fichiers
	$(PYTHON) scripts/notion_sync.py $(ARGS)
contracts:        ## gate contrats OHLCV (intégrité watchlist) — exit≠0 si violation (#10)
	$(PYTHON) scripts/contracts_check.py $(ARGS)
supabase-kpis:    ## pousse les KPIs du jour vers Supabase (SUPABASE_URL + SUPABASE_KEY requis) (#7)
	$(PYTHON) scripts/kpi_to_supabase.py
clean:
	find . -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null; rm -rf out
