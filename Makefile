.PHONY: install setup test lint demos api api-lan web preview interactive ingest daily cron tearsheet backtest-ml live live-go clean
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
api:              ## lance l'API FastAPI (localhost)
	$(PYTHON) -m uvicorn apps.api.main:app --reload
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
tearsheet:        ## exporte un tear sheet de performance (out/tearsheet.html + .pdf si reportlab)
	$(PYTHON) scripts/export_tearsheet.py
backtest-ml:      ## backtest ML walk-forward point-in-time (conviction+ML vs technique vs bench)
	$(PYTHON) scripts/backtest_ml.py
live:             ## APERÇU des ordres à répliquer (dry-run, aucun ordre envoyé)
	$(PYTHON) scripts/run_live.py --equity 10000
live-go:          ## EXÉCUTE en paper (Alpaca paper + Bitmart) — clés API requises
	$(PYTHON) scripts/run_live.py --live --yes
clean:
	find . -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null; rm -rf out
