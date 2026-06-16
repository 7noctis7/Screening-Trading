.PHONY: install test lint demos api web preview clean
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
api:              ## lance l'API FastAPI
	uvicorn apps.api.main:app --reload
web:              ## lance le front Next.js
	cd apps/web && npm install && npm run dev
clean:
	find . -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null; rm -rf out
