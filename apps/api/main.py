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
_SNAP_VERSION = "2026-06-20-drop-growth-columns"


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
    if _CACHE is None:                                   # aucun cache → build synchrone UNIQUE (verrou)
        with _BUILD_LOCK:                                # empêche 2 builds concurrents = 2× mémoire (OOM)
            if _CACHE is None:                           # double-check : un autre thread a pu finir
                _BUILDING = True
                try:
                    s = build_snapshot()
                    _CACHE, _CACHE_TS = s, time.time()
                    _persist(_CACHE, _CACHE_TS)
                finally:
                    _BUILDING = False
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
    if s is not None:                                    # cache valide → sert + rafraîchit en fond
        _CACHE, _CACHE_TS = s, ts
        if not _BUILDING:
            _BUILDING = True
            threading.Thread(target=_rebuild, daemon=True).start()
    # sinon : PAS de cache → on NE lance PAS de build de fond ; la 1re requête le construira UNE
    # seule fois (sous verrou) → évite 2 builds simultanés = 2× mémoire = OOM sur grosses données.


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/meta")
def meta() -> dict:
    return _snap()["meta"]


@app.get("/api/dashboard")
def dashboard() -> dict:
    d = dict(_snap()["dashboard"])
    d.pop("chart_series", None)      # lourd & inutile ici (utilisé par Positions/Trades/Live)
    return d


@app.get("/api/screener")
def screener() -> dict:
    return _snap()["screener"]


@app.get("/api/preset_ledger")
def preset_ledger() -> dict:
    """Journal détaillé du preset (trades + P&L réel) qui justifie la perf du dashboard."""
    return _snap().get("preset_ledger", {"available": False})


@app.get("/api/portfolio")
def portfolio() -> dict:
    return _snap()["portfolio"]


@app.get("/api/positions")
def positions() -> dict:
    snap = _snap()
    dash = snap["dashboard"]
    real = snap["live"]["real"]
    return {"real_positions": real.get("positions", []),    # positions RÉELLES (Alpaca + Bitmart)
            "connected": real.get("connected", False),
            "accounts": {"alpaca": real.get("alpaca", {}), "bitmart": real.get("bitmart", {})},
            "alloc_capital": dash.get("alloc_capital", {}),
            "series": dash.get("chart_series", {}),
            "markers": dash.get("real_markers", {})}


@app.get("/api/trades")
def trades() -> dict:
    snap = _snap()
    d = snap["dashboard"]
    real = snap["live"]["real"]
    return {"real_trades": real.get("trades", []),          # ordres RÉELS exécutés (Alpaca + Bitmart)
            "real_open_orders": real.get("open_orders", []),  # ordres RÉELS en attente d'exécution (non remplis)
            "connected": real.get("connected", False),
            "accounts": {"alpaca": real.get("alpaca", {}), "bitmart": real.get("bitmart", {})},
            "series": d.get("chart_series", {}),
            "markers": d.get("real_markers", {})}


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


_EVENTS: dict | None = None
_EVENTS_TS: float = 0.0


@app.get("/api/events")
def events() -> dict:
    """Calendrier d'événements RÉELS : résultats trimestriels (BPA/revenu estimés & annoncés) des
    sociétés de la base + positions réelles, et IPOs US (S-1/S-1/A SEC EDGAR + FMP). Cache 6 h."""
    global _EVENTS, _EVENTS_TS
    if _EVENTS is None or (time.time() - _EVENTS_TS) > 21600:
        import os
        from datetime import datetime, timezone

        from packages.events import earnings_for, upcoming_ipos
        snap = _snap()
        names: dict[str, str] = {}
        for r in (snap.get("conviction", {}).get("rows", []) + snap.get("fundamentals", {}).get("rows", [])
                  + snap.get("investors", {}).get("rows", [])):
            if r.get("symbol") and r.get("name"):
                names.setdefault(r["symbol"], r["name"])

        def _top_syms(pairs, pct=0.05, n_min=3) -> set:
            """Top 5 % (au moins n_min) d'une liste (symbole, score) — meilleurs scores d'abord."""
            p = sorted([(s, v) for s, v in pairs if s and v is not None], key=lambda x: x[1], reverse=True)
            return {s for s, _ in p[:max(n_min, round(len(p) * pct))]}

        _conv = snap.get("conviction", {}).get("rows", [])
        _scr = snap.get("screener", {}).get("rows", [])
        # TOP 5 % par lentille (ML, fondamentaux, investisseurs) + meilleures convictions globales
        top_ml = _top_syms([(r["symbol"], r.get("ml")) for r in _conv]
                           + [(r["symbol"], r.get("ml_score")) for r in _scr])
        top_fund = _top_syms([(r["symbol"], r.get("combined_score")) for r in snap.get("fundamentals", {}).get("rows", [])]
                             + [(r["symbol"], r.get("fundamental")) for r in _conv])
        top_inv = _top_syms([(r["symbol"], r.get("overall")) for r in snap.get("investors", {}).get("rows", [])]
                            + [(r["symbol"], r.get("investor")) for r in _conv])
        top_conv = _top_syms([(r["symbol"], r.get("conviction")) for r in _conv])
        # ÉTIQUETTES (pourquoi une société est suivie) — positions réelles + top scores
        tags: dict[str, list] = {}
        real_eq = {p.get("symbol") for p in snap.get("live", {}).get("real", {}).get("positions", [])
                   if p.get("symbol") and (p.get("asset_class") or "equity") in ("equity", "etf")}
        for s in real_eq:
            tags.setdefault(s, []).append("position")
        for s in top_conv:
            tags.setdefault(s, []).append("conviction")
        for s in top_ml:
            tags.setdefault(s, []).append("ML")
        for s in top_fund:
            tags.setdefault(s, []).append("fond.")
        for s in top_inv:
            tags.setdefault(s, []).append("invest.")
        # univers : on met EN TÊTE les positions + top scores (pour passer le plafond yfinance à 40)
        eq: list[str] = list(dict.fromkeys(list(tags)))
        for r in snap.get("universe", {}).get("instruments", []):
            sym = r.get("symbol"); ac = (r.get("asset_class") or "equity")
            if sym and ac in ("equity", "etf"):
                eq.append(sym); names.setdefault(sym, r.get("name", "") or "")
        eq = list(dict.fromkeys(eq))
        try:
            earn = earnings_for(eq)
        except Exception as e:  # noqa: BLE001
            log.warning("earnings_for failed: %s", e); earn = []
        for ev in earn:
            sym = ev.get("symbol", "")
            ev["name"] = names.get(sym, "")
            ev["tags"] = tags.get(sym, [])
        try:
            ipos = upcoming_ipos()
        except Exception as e:  # noqa: BLE001
            log.warning("upcoming_ipos failed: %s", e); ipos = []
        _EVENTS = {"available": bool(earn or ipos), "earnings": earn, "ipos": ipos,
                   "n_symbols": len(eq), "fmp": bool(os.environ.get("FMP_API_KEY")),
                   "fmp_earnings": any(e.get("source") == "FMP" for e in earn),
                   "fmp_ipos": any(p.get("source") == "FMP" for p in ipos),
                   "as_of": datetime.now(timezone.utc).isoformat()}
        _EVENTS_TS = time.time()
    return _EVENTS


@app.get("/api/overlays")
def overlays(ticker: str = "") -> dict:
    """Overlays graphiques (marqueurs ▲▼, cônes de risque, blackouts) écrits par le serveur MCP
    TradingView → lus par lightweight-charts. Display-only (jamais utilisé par backtest/ML)."""
    from packages.mcp_tradingview.store import OverlayStore
    st = OverlayStore()
    return st.get(ticker) if ticker else st.all()


@app.post("/api/tv/webhook")
async def tv_webhook(request: Request) -> dict:
    """Webhook entrant des alertes TradingView (Pine/indicateur) → drop pour le risk-engine (veto)."""
    from packages.mcp_tradingview.alerts import append_alert
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        body = {}
    a = append_alert(body if isinstance(body, dict) else {})
    return {"ok": a is not None, "alert": a.to_dict() if a else None}


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
