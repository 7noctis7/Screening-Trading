"""API FastAPI — sert les payloads au front (aucune logique de trading ici).

Requiert fastapi + uvicorn (ton env). Lancer :  uvicorn apps.api.main:app --reload
En offline, les routes renvoient le snapshot synthétique ; en prod, brancher l'état live.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.api.snapshot import build_snapshot

app = FastAPI(title="Quant Trading API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
                   allow_headers=["*"])

_CACHE: dict | None = None


def _snap() -> dict:
    global _CACHE
    if _CACHE is None:
        _CACHE = build_snapshot()
    return _CACHE


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/dashboard")
def dashboard() -> dict:
    return _snap()["dashboard"]


@app.get("/api/screener")
def screener() -> dict:
    return _snap()["screener"]


@app.get("/api/portfolio")
def portfolio() -> dict:
    return _snap()["portfolio"]


@app.get("/api/positions")
def positions() -> dict:
    return {"positions": _snap()["dashboard"]["positions"],
            "totals": _snap()["dashboard"]["totals"]}


@app.get("/api/trades")
def trades() -> dict:
    snap = _snap()
    return {"trades": snap["trades"], "open_trades": snap["open_trades"],
            "stats": snap["trade_stats"]}


@app.get("/api/universe")
def universe() -> dict:
    return _snap()["universe"]


@app.get("/api/data")
def data() -> dict:
    return _snap()["data"]
