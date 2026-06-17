"""API FastAPI — sert les payloads au front (aucune logique de trading ici).

Requiert fastapi + uvicorn (ton env). Lancer :  uvicorn apps.api.main:app --reload
En offline, les routes renvoient le snapshot synthétique ; en prod, brancher l'état live.
"""

from __future__ import annotations

import time

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.api.snapshot import build_snapshot

app = FastAPI(title="Quant Trading API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
                   allow_headers=["*"])

_CACHE: dict | None = None
_CACHE_TS: float = 0.0
_TTL_S = 900  # 15 min : aligne le rafraîchissement serveur sur le flux différé


def _snap() -> dict:
    """Snapshot caché avec TTL → le polling du front récupère des données fraîches."""
    global _CACHE, _CACHE_TS
    if _CACHE is None or (time.time() - _CACHE_TS) > _TTL_S:
        _CACHE = build_snapshot()
        _CACHE_TS = time.time()
    return _CACHE


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/meta")
def meta() -> dict:
    return _snap()["meta"]


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
    dash = _snap()["dashboard"]
    return {"positions": dash["positions"], "totals": dash["totals"],
            "portfolio": dash["portfolio"], "series": dash["position_series"],
            "markers": dash["position_markers"]}


@app.get("/api/trades")
def trades() -> dict:
    snap = _snap()
    return {"trades": snap["trades"], "open_trades": snap["open_trades"],
            "stats": snap["trade_stats"],
            "series": snap["dashboard"]["position_series"],
            "markers": snap["dashboard"]["position_markers"]}


@app.get("/api/sentiment")
def sentiment() -> dict:
    return _snap()["sentiment"]


@app.get("/api/fundamentals")
def fundamentals() -> dict:
    return _snap()["fundamentals"]


@app.get("/api/universe")
def universe() -> dict:
    return _snap()["universe"]


@app.get("/api/data")
def data() -> dict:
    return _snap()["data"]


@app.get("/api/themes")
def themes() -> dict:
    return _snap()["themes"]


@app.get("/api/ml")
def ml() -> dict:
    return _snap()["ml"]


@app.get("/api/live")
def live() -> dict:
    return _snap()["live"]


@app.get("/api/ai/status")
def ai_status() -> dict:
    """Disponibilité d'un LLM local (LM Studio / Ollama)."""
    from packages.llm import available
    return {"available": available()}


@app.get("/api/ai/commentary")
def ai_commentary() -> dict:
    """Commentaire IA en langage naturel sur l'état du portefeuille (LLM local uniquement)."""
    from packages.llm import complete
    s = _snap()
    d, p = s["dashboard"], s["portfolio"]
    rm = p.get("analysis", {}).get("risk", {})
    k = d.get("portfolio", {})
    top = ", ".join(f"{r['symbol']} ({r.get('score', 0):.2f})" for r in s["screener"]["rows"][:5])
    reg = d.get("regime", {})
    facts = (
        f"Portefeuille (démo): {k.get('value', 0):.0f} $, P&L {k.get('pnl_pct', 0)*100:.1f}%, "
        f"{k.get('n_positions', 0)} positions, exposition {k.get('exposure_pct', 0)*100:.0f}%.\n"
        f"Régime: {reg.get('cycle', '?')} / {reg.get('risk_mode', '?')}, VIX {d.get('vix', 0):.0f}.\n"
        f"Risque: VaR95 {rm.get('var_95', 0)*100:.1f}%, vol {rm.get('vol', 0)*100:.1f}%, "
        f"Sharpe déflaté {rm.get('dsr', 0)}.\n"
        f"Top screener: {top}."
    )
    system = ("Tu es un analyste quant senior. Commente en français, en 4-6 phrases claires et "
              "actionnables, l'état du portefeuille ci-dessous (risque, régime, idées). "
              "Pas de conseil personnalisé, ton factuel et prudent.")
    res = complete(facts, system=system, max_tokens=350)
    return {"available": res.get("available", False), "text": res.get("text", ""),
            "reason": res.get("reason", "")}
