.PHONY: install test lint demos api api-lan web preview interactive ingest daily clean
install:          ## installe les dépendances (uv)
	uv venv && uv pip install -e ".[dev,data,quant,api,ml]"
test:             ## lance la suite de tests
	pytest -q
lint:             ## ruff + mypy
	ruff check packages apps && mypy packages
demos:            ## exécute les démos offline
	python scripts/demo_backtest.py && python scripts/demo_walkforward.py && \
	python scripts/demo_macro_regime.py && python scripts/demo_ml.py && \
	python scripts/demo_paper_loop.py && python scripts/demo_alerts.py && python scripts/demo_ops.py
preview:          ## régénère les aperçus HTML du dashboard/portefeuille
	python apps/web/preview/build_preview.py
api:              ## lance l'API FastAPI (localhost)
	uvicorn apps.api.main:app --reload
api-lan:          ## lance l'API accessible depuis le téléphone (même Wi-Fi) → http://IP_DU_MAC:8000
	uvicorn apps.api.main:app --host 0.0.0.0 --port 8000
web:              ## lance le front Next.js
	cd apps/web && npm install && npm run dev
interactive:      ## génère la preview autonome (apps/web/preview/interactive.html)
	python apps/web/preview/build_interactive.py
ingest:           ## backfill des prix réels (yfinance) → data/market.db
	python scripts/ingest_prices.py --since 2015-01-01
daily:            ## mise à jour incrémentale quotidienne des prix réels
	python scripts/ingest_prices.py --daily
clean:
	find . -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null; rm -rf out
