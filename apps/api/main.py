"""API FastAPI — sert les payloads au front (aucune logique de trading ici).

Requiert fastapi + uvicorn (ton env). Lancer :  uvicorn apps.api.main:app --reload
En offline, les routes renvoient le snapshot synthétique ; en prod, brancher l'état live.
"""

from __future__ import annotations

import logging
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from apps.api.snapshot import build_snapshot

# --- Journalisation fichier (logs/app.log, rotation 2 Mo × 5) pour suivi & investigation ---
_LOG_DIR = Path(__file__).resolve().parents[2] / "logs"
_LOG_DIR.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s : %(message)s",
    handlers=[RotatingFileHandler(_LOG_DIR / "app.log", maxBytes=2_000_000, backupCount=5),
              logging.StreamHandler()],
)
log = logging.getLogger("quant.api")
for _noisy in ("watchfiles", "watchfiles.main"):   # silence le rechargeur (logs propres)
    logging.getLogger(_noisy).setLevel(logging.WARNING)

app = FastAPI(title="Quant Trading API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
                   allow_headers=["*"])


@app.middleware("http")
async def _log_requests(request: Request, call_next):
    """Journalise chaque requête (chemin, statut, durée) et capture les erreurs."""
    t0 = time.time()
    try:
        resp = await call_next(request)
    except Exception as e:  # noqa: BLE001
        log.exception("ERREUR %s %s : %s", request.method, request.url.path, e)
        return JSONResponse(status_code=500, content={"error": str(e)[:200]})
    dt = (time.time() - t0) * 1000
    lvl = logging.WARNING if resp.status_code >= 400 else logging.INFO
    log.log(lvl, "%s %s → %s (%.0f ms)", request.method, request.url.path, resp.status_code, dt)
    return resp

import pickle
import threading

_CACHE: dict | None = None
_CACHE_TS: float = 0.0
_TTL_S = 900  # 15 min : aligne le rafraîchissement serveur sur le flux différé
_BUILDING = False
_BUILD_LOCK = threading.Lock()
_SNAP_FILE = Path(__file__).resolve().parents[2] / ".cache" / "snapshot.pkl"
# Bump à chaque changement de SCHÉMA du snapshot → invalide le cache disque (évite de servir un
# ancien snapshot construit par une version antérieure du code).
_SNAP_VERSION = "2026-06-19-index-core-satellite"


def _load_disk() -> tuple[dict | None, float]:
    try:
        with _SNAP_FILE.open("rb") as f:
            d = pickle.load(f)  # noqa: S301 — artefact local de confiance
        if d.get("version") != _SNAP_VERSION:           # code changé → ignore l'ancien cache
            return None, 0.0
        return d["snap"], float(d["ts"])
    except Exception:  # noqa: BLE001
        return None, 0.0


def _persist(snap: dict, ts: float) -> None:
    try:
        _SNAP_FILE.parent.mkdir(parents=True, exist_ok=True)
        with _SNAP_FILE.open("wb") as f:
            pickle.dump({"snap": snap, "ts": ts, "version": _SNAP_VERSION}, f)
    except Exception:  # noqa: BLE001
        pass


def _rebuild() -> None:
    """Reconstruit le snapshot en arrière-plan et remplace le cache (+ persiste)."""
    global _CACHE, _CACHE_TS, _BUILDING
    try:
        s = build_snapshot()
        ts = time.time()
        _CACHE, _CACHE_TS = s, ts
        _persist(s, ts)
        log.info("snapshot rebuilt (%.0fs ttl)", _TTL_S)
    except Exception as e:  # noqa: BLE001
        log.exception("snapshot rebuild failed: %s", e)
    finally:
        _BUILDING = False


def _snap() -> dict:
    """Snapshot servi INSTANTANÉMENT depuis le cache (mémoire→disque), rafraîchi en arrière-plan
    (stale-while-revalidate) → plus jamais d'attente d'1-2 min après un redémarrage."""
    global _CACHE, _CACHE_TS, _BUILDING
    if _CACHE is None:                                   # 1er accès du process : tente le disque
        s, ts = _load_disk()
        if s is not None:
            _CACHE, _CACHE_TS = s, ts
    if _CACHE is None:                                   # aucun cache → build synchrone (1re fois)
        _CACHE = build_snapshot()
        _CACHE_TS = time.time()
        _persist(_CACHE, _CACHE_TS)
        return _CACHE
    if (time.time() - _CACHE_TS) > _TTL_S and not _BUILDING:   # périmé → refresh en fond, sert l'ancien
        with _BUILD_LOCK:
            if not _BUILDING:
                _BUILDING = True
                threading.Thread(target=_rebuild, daemon=True).start()
    return _CACHE


@app.on_event("startup")
def _warm() -> None:
    """Au démarrage : charge le dernier snapshot du disque (service instantané) et déclenche un
    rafraîchissement en arrière-plan → le 1er chargement du site est immédiat."""
    global _CACHE, _CACHE_TS, _BUILDING
    s, ts = _load_disk()
    if s is not None:
        _CACHE, _CACHE_TS = s, ts
    if not _BUILDING:
        _BUILDING = True
        threading.Thread(target=_rebuild, daemon=True).start()


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
            "preset_allocation": dash.get("preset_allocation", []),
            "alloc_capital": dash.get("alloc_capital", {}),
            "portfolio": dash["portfolio"],
            "series": {**dash.get("chart_series", {}), **dash["position_series"]},
            "markers": dash["position_markers"]}


@app.get("/api/trades")
def trades() -> dict:
    snap = _snap()
    d = snap["dashboard"]
    return {"trades": snap["trades"], "open_trades": snap["open_trades"],
            "stats": snap["trade_stats"], "preset_trades": snap.get("preset_trades", {}),
            "series": {**d.get("chart_series", {}), **d["position_series"]},
            "markers": d["position_markers"]}


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
    snap = _snap()
    return {**snap["live"], "series": snap["dashboard"].get("chart_series", {})}


@app.get("/api/conviction")
def conviction() -> dict:
    return _snap()["conviction"]


@app.get("/api/investors")
def investors() -> dict:
    return _snap()["investors"]


_MACRO: dict | None = None
_MACRO_TS: float = 0.0


@app.get("/api/macro")
def macro() -> dict:
    """Données macro chiffrées (FRED) — cache 6 h (séries publiées quotidiennement au plus)."""
    global _MACRO, _MACRO_TS
    if _MACRO is None or (time.time() - _MACRO_TS) > 21600:
        from packages.macro import macro_snapshot
        from packages.macro.imf import imf_projections
        _MACRO = {"fred": macro_snapshot(), "imf": imf_projections()}
        _MACRO_TS = time.time()
    return _MACRO


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
    system = ("Tu es un analyste quant senior. Réponds DIRECTEMENT en français, 4-6 phrases "
              "claires et actionnables, sans afficher ton raisonnement. Commente l'état du "
              "portefeuille (risque, régime, idées). Ton factuel et prudent, pas de conseil personnalisé.")
    res = complete(facts, system=system, max_tokens=1100)
    return {"available": res.get("available", False), "text": res.get("text", ""),
            "reason": res.get("reason", "")}
