.PHONY: install setup test lint demos start stop api api-dev api-lan web preview interactive ingest daily cron cron-install cron-uninstall tearsheet train backtest-ml backtest-weighting backtest-earnings backtest-breakout backtest-sentiment backtest-preset backtest-megacap index-core index-core-stress index-core-regime crypto-core ledger-sweep ingest-crypto ingest-mktcap preset-report calibrate-preset screen-niche list-db live live-go clean
PYTHON ?= python3      ## sur macOS c'est python3 (surchargeable : make api PYTHON=python)
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
clean:
	find . -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null; rm -rf out
