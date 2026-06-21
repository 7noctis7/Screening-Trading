"""API FastAPI — sert les payloads au front (aucune logique de trading ici).

Requiert fastapi + uvicorn (ton env). Lancer :  uvicorn apps.api.main:app --reload
En offline, les routes renvoient le snapshot synthétique ; en prod, brancher l'état live.
"""

from __future__ import annotations

import logging
import os
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
_SNAP_VERSION = "2026-06-21-history-2015"


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


@app.get("/api/analytics")
def analytics() -> dict:
    """Reporting de performance (Sortino/Calmar/Alpha/Beta vs QQQ, MaxDD) — net de frais.
    Renvoie métriques + un snippet HTML prêt pour le front. Tolérant : {available:false} si indispo."""
    from packages.reporting.analytics import PerformanceAnalytics
    cur = _snap().get("index_core_curves", {}) or {}
    preset, qqq = cur.get("preset") or [], cur.get("qqq") or []
    if len(preset) < 30:
        return {"available": False}
    pa = PerformanceAnalytics.from_curves(preset, qqq)
    return {"available": True, "metrics": pa.metrics().to_dict(),
            "attribution": pa.attribution(),
            "html": pa.to_html_snippet("Preset vs QQQ (net de frais)")}


def _sma(values: list[float], n: int) -> float | None:
    return sum(values[-n:]) / n if len(values) >= n else None


def _rsi(values: list[float], n: int = 14) -> float | None:
    if len(values) < n + 1:
        return None
    gains = losses = 0.0
    for i in range(-n, 0):
        d = values[i] - values[i - 1]
        gains += max(0.0, d); losses += max(0.0, -d)
    if losses == 0:
        return 100.0
    rs = (gains / n) / (losses / n)
    return round(100 - 100 / (1 + rs), 1)


def _company_closes(sym: str) -> tuple[list[float], list[str]]:
    """Clôtures RÉELLES + dates d'un titre (market.db puis crypto.db). ([],[]) si absent."""
    try:
        from packages.data.engine import read_prices_rows
        rows = read_prices_rows("market.db", symbols=[sym]) or read_prices_rows("crypto.db", symbols=[sym])
        rows = [r for r in sorted(rows, key=lambda r: r.get("ts") or "") if r.get("close") is not None]
        return [float(r["close"]) for r in rows], [str(r.get("ts") or "")[:10] for r in rows]
    except Exception:  # noqa: BLE001
        return [], []


def _company_technical(sym: str, closes: list[float] | None = None) -> dict | None:
    """Résumé technique d'un titre depuis la base de prix RÉELLE (tendance, RSI, MACD, position vs
    moyennes mobiles, plage 52 sem.). Pur-Python, best-effort → None si indisponible."""
    try:
        closes = closes if closes is not None else _company_closes(sym)[0]
        if len(closes) < 60:
            return None
        last = closes[-1]
        s50 = _sma(closes, 50); s200 = _sma(closes, 200)
        ema12 = _ema(closes, 12); ema26 = _ema(closes, 26)
        macd = (ema12 - ema26) if (ema12 is not None and ema26 is not None) else None
        win = closes[-252:] if len(closes) >= 252 else closes
        trend = "haussière" if (s50 and last > s50 and (not s200 or last > s200)) else (
            "baissière" if (s50 and last < s50) else "neutre")
        return {"trend": trend, "rsi": _rsi(closes),
                "macd_signal": ("haussier" if (macd or 0) > 0 else "baissier") if macd is not None else None,
                "vs_sma50": (last / s50 - 1) if s50 else None,
                "vs_sma200": (last / s200 - 1) if s200 else None,
                "low_52w": min(win), "high_52w": max(win)}
    except Exception:  # noqa: BLE001
        return None


def _ema(values: list[float], n: int) -> float | None:
    if len(values) < n:
        return None
    k = 2 / (n + 1)
    e = values[0]
    for v in values[1:]:
        e = v * k + e * (1 - k)
    return e


def _company_macro() -> dict | None:
    """Contexte macro courant (régime, VIX, exposition conseillée) depuis le snapshot."""
    try:
        snap = _snap()
        d = snap.get("dashboard", {})
        reg = d.get("regime", {}) or {}
        label = reg.get("label") or reg.get("regime") or reg.get("risk_mode") or reg.get("cycle")
        # Complétude obligatoire (pas de "—") : exposition dérivée du régime si absente
        exp = reg.get("exposure")
        if exp is None:
            exp = {"risk_on": 1.0, "neutral": 0.6, "risk_off": 0.3, "panic": 0.3}.get(
                str(reg.get("risk_mode") or label).lower(), 0.6)
        # taux 10 ans : section macro du snapshot, sinon dernier repli connu
        rate_10y = None
        try:
            mac = snap.get("macro", {}) or {}
            for k in ("us10y", "rate_10y", "ten_year", "dgs10"):
                v = (mac.get(k) if isinstance(mac, dict) else None)
                if isinstance(v, (int, float)):
                    rate_10y = float(v) / (100.0 if v > 1.5 else 1.0)
                    break
        except Exception:  # noqa: BLE001
            pass
        if rate_10y is None:
            rate_10y = 0.043     # repli : dernier 10Y US connu (évite une valeur vide)
        return {"regime": label or "neutre", "vix": d.get("vix") or 18.0,
                "exposure": exp, "rate_10y": rate_10y}
    except Exception:  # noqa: BLE001
        return None


def _company_peers(sym: str) -> list[dict] | None:
    """Pairs sectoriels (mêmes métriques) depuis la section fondamentaux du snapshot, pour le
    positionnement vs secteur. None si indisponible."""
    try:
        rows = (_snap().get("fundamentals", {}) or {}).get("rows", []) or []
        sec = next((r.get("sector") for r in rows if r.get("symbol") == sym), None)
        if not sec:
            return None
        peers = [{"net_margin": r.get("net_margin"), "roe": r.get("roe"), "roic": r.get("roic"),
                  "gross_margin": r.get("gross_margin"), "per": r.get("per"),
                  "ev_ebitda": r.get("ev_ebitda")}
                 for r in rows if r.get("sector") == sec]
        return peers if len(peers) >= 3 else None
    except Exception:  # noqa: BLE001
        return None


def _company_financial_history(sym: str) -> list[dict] | None:
    """Historique financier 5-6 ans RÉEL via SEC EDGAR (CA/résultat/BPA par exercice). None si
    émetteur non-SEC (le builder dérivera alors N-1/N). Best-effort."""
    try:
        from packages.fundamentals.sec_provider import financial_history
        h = financial_history(sym, years=6)
        return h or None
    except Exception:  # noqa: BLE001
        return None


def _company_quarterly(sym: str) -> list[dict] | None:
    """4 derniers TRIMESTRES : yfinance d'abord, repli SEC EDGAR (10-Q). CA, résultat net, BPA, marge."""
    yq = _quarterly_yf(sym)
    if yq and len([x for x in yq if x.get("revenue")]) >= 2:
        return yq
    try:                                                    # repli SEC EDGAR (officiel, gratuit)
        from packages.fundamentals.sec_provider import quarterly_history
        sq = quarterly_history(sym, n=4)
        if sq and len([x for x in sq if x.get("revenue")]) >= 2:
            return sq
    except Exception:  # noqa: BLE001
        pass
    return yq


def _quarterly_yf(sym: str) -> list[dict] | None:
    """4 derniers trimestres via yfinance (quarterly_income_stmt)."""
    try:
        import yfinance as yf
        df = yf.Ticker(sym).quarterly_income_stmt
        if df is None or getattr(df, "empty", True):
            return None

        def _row(*names):
            for n in names:
                if n in df.index:
                    return df.loc[n]
            return None
        rev = _row("Total Revenue", "TotalRevenue")
        ni = _row("Net Income", "NetIncome", "Net Income Common Stockholders")
        eps = _row("Diluted EPS", "Basic EPS")
        out = []
        for col in list(df.columns)[:4]:
            def _v(s):
                try:
                    return float(s[col]) if s is not None and s[col] == s[col] else None
                except Exception:  # noqa: BLE001
                    return None
            rv, nv = _v(rev), _v(ni)
            out.append({"period": f"{col.year}-T{getattr(col, 'quarter', '?')}",
                        "revenue": rv, "net_income": nv, "eps": _v(eps),
                        "net_margin": (nv / rv if (rv and nv is not None) else None)})
        out.reverse()                                   # plus ancien → plus récent
        return out or None
    except Exception:  # noqa: BLE001
        return None


def _company_holders(sym: str, shares_out: float | None = None) -> dict | None:
    """Top 5 INSTITUTIONNELS + top 5 INSIDERS (yfinance), en % du capital. Best-effort réseau."""
    try:
        import yfinance as yf
        t = yf.Ticker(sym)
        so = shares_out if (shares_out and shares_out > 0) else None
        if so is None:                                     # actions en circulation pour convertir les insiders
            try:
                so = float(t.fast_info.get("shares") or t.fast_info.get("sharesOutstanding") or 0) or None
            except Exception:  # noqa: BLE001
                so = None
        inst, ins = [], []
        try:
            df = t.institutional_holders
            if df is not None and not getattr(df, "empty", True):
                for _, row in df.head(5).iterrows():
                    pct = row.get("pctHeld") if "pctHeld" in row else row.get("% Out")
                    p = float(pct) if (pct is not None and pct == pct) else None
                    inst.append({"name": str(row.get("Holder", "")), "pct": p})
        except Exception:  # noqa: BLE001
            pass
        try:
            df = t.insider_roster_holders
            if df is not None and not getattr(df, "empty", True):
                col = next((c for c in ("Shares Owned Directly", "Shares Owned Indirectly",
                                        "Position Direct") if c in df.columns), None)
                for _, row in df.head(5).iterrows():
                    sh = float(row.get(col)) if (col and row.get(col) == row.get(col)) else None
                    pct = (sh / so) if (sh and so) else None    # insider en % du capital
                    ins.append({"name": str(row.get("Name", "")), "pct": pct, "shares": sh})
        except Exception:  # noqa: BLE001
            pass
        if not inst and not ins:
            return None
        return {"institutional": inst, "insiders": ins}
    except Exception:  # noqa: BLE001
        return None


def _company_earnings(sym: str) -> dict | None:
    """Prochaine date de résultats + BPA/revenu estimés & annoncés (réels) pour un titre."""
    try:
        from packages.events import earnings_for
        rows = earnings_for([sym]) or []
        if not rows:
            return None
        row = sorted(rows, key=lambda r: r.get("date") or "")[-1]   # le plus récent/à venir
        return {"next_date": row.get("date"), "eps_estimate": row.get("eps_estimate"),
                "eps_actual": row.get("eps_actual"), "revenue_estimate": row.get("revenue_estimate"),
                "revenue_actual": row.get("revenue_actual")}
    except Exception:  # noqa: BLE001
        return None


# Cache des notes par société, INVALIDÉ PAR LES RÉSULTATS TRIMESTRIELS : la clé inclut la date
# du dernier résultat publié → dès qu'une société publie un nouveau trimestre, la note se régénère
# automatiquement (et reste servie depuis le cache entre deux publications, sans recalcul).
_REPORT_CACHE: dict[str, tuple[str, dict]] = {}
_REPORT_CACHE_MAX = 256


def _build_company_report_cached(sym: str) -> tuple[dict | None, str | None]:
    """Construit (ou ressort du cache) la note. Renvoie (report, error). Cache clé = ticker +
    signature de résultats (date + BPA/revenu annoncés) → régénération à chaque nouvelle publication."""
    from apps.api.snapshot import _seed_universe, fetch_financials_chain
    from packages.reporting import build_company_report
    earnings = _company_earnings(sym)
    sig = "|".join(str(x) for x in [
        (earnings or {}).get("date") or (earnings or {}).get("next_date"),
        (earnings or {}).get("eps_actual"), (earnings or {}).get("revenue_actual")])
    cached = _REPORT_CACHE.get(sym)
    if cached and cached[0] == sig:
        return cached[1], None
    f, prior, src = fetch_financials_chain(sym)
    if f is None:
        return None, f"aucune donnée pour {sym}"
    f_recon = f                                            # financials AVANT conversion (devise de dépôt)
    # CONVERSION DEVISE (ADR) : comptes en devise locale ≠ cours → on convertit pour une valorisation
    # correcte (au lieu de masquer). Best-effort : si pas de taux (hors-ligne), la gate masquera.
    fx_note = None
    if f.currency and f.price_currency and f.currency != f.price_currency:
        try:
            from packages.data.fx import rate
            from packages.fundamentals.corporate_finance import convert_financials
            fx = rate(f.currency, f.price_currency)
            if fx and fx > 0:
                f = convert_financials(f, fx)
                if prior is not None:
                    prior = convert_financials(prior, fx)
                fx_note = f"comptes convertis en {f.price_currency} (taux {fx:.4f})"
        except Exception:  # noqa: BLE001
            pass
    # nom : raison sociale de la source (yfinance/SEC) > univers seed > ticker ; sinon SEC name map
    name = getattr(f, "name", None) or next(
        (m.get("name") for m in _seed_universe() if m.get("symbol") == sym), None)
    if not name or name == sym:
        try:
            from packages.fundamentals.sec_provider import company_name
            name = company_name(sym) or name or sym
        except Exception:  # noqa: BLE001
            name = name or sym
    beta, ml_score = 1.0, None
    try:
        snap = _snap()
        rm = snap.get("portfolio", {}).get("analysis", {}).get("risk", {})
        beta = float(rm.get("beta") or 1.0)
        ml_score = (snap.get("ml", {}).get("scores", {}) or {}).get(sym)   # proba ML du titre
    except Exception:  # noqa: BLE001
        pass
    closes, dates = _company_closes(sym)
    fin_hist = _company_financial_history(sym)
    report = build_company_report(f, name=name, prior=prior, beta=beta,
                                  technical=_company_technical(sym, closes), macro=_company_macro(),
                                  earnings=earnings, ml_score=ml_score, price_series=closes,
                                  price_dates=dates, financial_history=fin_hist, peers=_company_peers(sym))
    report["source"] = src
    report["earnings_signature"] = sig
    # mode LITE (builds batch site/CI) : on saute les appels yfinance lents (actionnariat, trimestriel)
    if os.environ.get("QUANT_REPORT_LITE") != "1":
        holders = _company_holders(sym, getattr(f, "shares", None))
        if holders:
            report["holders"] = holders
        quarterly = _company_quarterly(sym)
        if quarterly:
            report["quarterly"] = quarterly
    if fx_note:
        report["fx_conversion"] = fx_note
        report.setdefault("audit", {}).setdefault("findings", []).append(
            {"severity": "warning", "detail": fx_note})
    _enrich_cross_source(report, f_recon, sym)         # réconciliation en devise de dépôt (EUR vs EUR)
    _enrich_ai_memo(report)                             # mémo IA local si dispo (sinon règles)
    if len(_REPORT_CACHE) >= _REPORT_CACHE_MAX:
        _REPORT_CACHE.pop(next(iter(_REPORT_CACHE)))
    _REPORT_CACHE[sym] = (sig, report)
    return report, None


def _enrich_cross_source(report: dict, f: Any, sym: str) -> None:
    """VENTILATION GAAP vs NON-GAAP : compare CA & résultat net de la source primaire (souvent TTM/
    ajusté = « non-GAAP ») au dépôt SEC EDGAR (10-K, GAAP). Construit la table de réconciliation et,
    si un écart > 10 % sur CA OU RN, lève une BLOCKING ALERT (protocole PwC). Best-effort."""
    try:
        from packages.fundamentals.sec_provider import financial_history, quarterly_history
        # PÉRIODE ALIGNÉE : la source primaire (yfinance) est en TTM → on compare au TTM SEC (somme des
        # 4 derniers trimestres 10-Q), pas au dernier exercice annuel (sinon faux écarts énormes).
        period = "TTM"
        q = quarterly_history(sym, n=4)
        qrev = [x.get("revenue") for x in q if x.get("revenue") is not None]
        qni = [x.get("net_income") for x in q if x.get("net_income") is not None]
        if len(q) >= 4 and len(qrev) == 4 and len(qni) == 4:
            sec = {"revenue": sum(qrev), "net_income": sum(qni)}
        else:                                              # repli : exercice annuel (périodes non alignées)
            hist = financial_history(sym, years=1)
            if not hist:
                return
            sec = hist[-1]; period = "annuel"
        rows, max_gap = [], 0.0
        for label, reported, gaap in (("Chiffre d'affaires", f.revenue, sec.get("revenue")),
                                      ("Résultat net", f.net_income, sec.get("net_income"))):
            if gaap is None or not gaap:
                continue
            gap = abs((reported or 0) - gaap) / abs(gaap)
            max_gap = max(max_gap, gap)
            status = "réconcilié" if gap <= 0.10 else ("écart majeur" if gap <= 0.25 else "écart critique")
            rows.append({"metric": label, "reported": reported, "gaap": gaap,
                         "gap": round(gap, 3), "status": status})
        if not rows:
            return
        report["reconciliation"] = {
            "rows": rows, "max_gap": round(max_gap, 3), "period": period,
            "note": (f"Comparaison en DEVISE DE DÉPÔT (avant conversion de change). "
                     f"« Reporté » = source primaire (yfinance, TTM) · « GAAP » = SEC EDGAR "
                     f"({'TTM, somme des 4 derniers 10-Q' if period=='TTM' else 'dernier 10-K'}, "
                     f"source de vérité comptable).")}
        report["cross_source_gap"] = round(max_gap, 3)
        audit = report.setdefault("audit", {})
        audit["counts"] = audit.get("counts", {})
        # Protocole PwC : > 10 % d'écart CA OU RN inter-sources → BLOCKING ALERT (gèle l'ordre)
        if max_gap > 0.10:
            sev = "critical" if max_gap > 0.25 else "warning"
            worst = max(rows, key=lambda x: x["gap"])
            audit.setdefault("findings", []).append({
                "severity": sev,
                "detail": (f"écart {worst['metric']} GAAP vs source {worst['gap']*100:.0f}% "
                           f"({_b(worst['reported'])} vs SEC {_b(worst['gaap'])}) — réconciliation requise")})
            audit["counts"][sev] = audit["counts"].get(sev, 0) + 1
            report.setdefault("flags", {})["blocking_alert"] = True
            report["score"]["verdict_status"] = "CONTRÔLE REQUIS"
            report["score"]["recommendation"] = "Contrôle requis"
    except Exception:  # noqa: BLE001
        pass


def _b(x) -> str:
    try:
        a = abs(float(x))
        for d, s in ((1e12, "T"), (1e9, "Md"), (1e6, "M")):
            if a >= d:
                return f"{float(x)/d:.1f}{s}"
        return f"{float(x):.0f}"
    except (TypeError, ValueError):
        return "—"


def _enrich_ai_memo(report: dict) -> None:
    """Remplace le mémo par une synthèse IA locale (LM Studio/Ollama) si un serveur répond. Sinon
    conserve la synthèse à base de règles. Jamais bloquant, rien ne sort de la machine."""
    if os.environ.get("QUANT_NO_LLM") == "1":      # builds batch (site/CI) : pas d'appel LLM (évite les blocages)
        return
    try:
        from packages.llm import available, complete
        if not available():
            return
        idy, sc = report.get("identity", {}), report.get("score", {})
        v = report.get("verdict", {})
        facts = (f"Société: {idy.get('name')} ({idy.get('symbol')}), secteur {idy.get('sector')}. "
                 f"Score {sc.get('global')}/100 (fond {sc.get('fundamental')}, tech {sc.get('technical')}, "
                 f"ml {sc.get('ml')}), reco {sc.get('recommendation')}. "
                 f"Vernimmen: ROCE {report.get('vernimmen',{}).get('roce_after_tax')} vs WACC "
                 f"{report.get('vernimmen',{}).get('wacc')}. DCF base marge de sécurité "
                 f"{report.get('damodaran',{}).get('dcf',{}).get('margin_of_safety')}. "
                 f"Forces: {', '.join(v.get('strengths', [])[:3])}. Vigilance: {', '.join(v.get('watch', [])[:3])}.")
        memo = complete(
            "Rédige une synthèse d'investisseur en 3 phrases maximum, factuelle et nuancée, à partir "
            "de ces données. Pas de conseil financier explicite.\n\n" + facts,
            system="Tu es un analyste financier senior (style Damodaran/Vernimmen). Concis, précis, français.",
            temperature=0.3)
        if memo and len(memo.strip()) > 30:
            report["memo"] = memo.strip()
            report["memo_source"] = "IA locale"
    except Exception:  # noqa: BLE001
        pass


@app.get("/api/company_report")
def company_report(ticker: str, format: str = "html", theme: str = "dark") -> Any:
    """Note d'analyse fondamentale par société (Vernimmen + Damodaran, intrants contrôlés).
    `format` : html (page autonome), json (données), pdf (weasyprint/reportlab si présent, sinon HTML).
    `theme` : dark (défaut) | light. Sources gratuites réelles (yfinance→FMP→SEC EDGAR), repli
    synthétique hors-ligne. Note mise en cache et REGÉNÉRÉE à chaque nouveau résultat trimestriel."""
    from fastapi.responses import HTMLResponse, FileResponse

    from packages.reporting import company_report_html, company_report_pdf
    sym = (ticker or "").strip().upper()
    if not sym:
        return JSONResponse({"available": False, "error": "ticker requis"}, status_code=400)
    report, err = _build_company_report_cached(sym)
    if report is None:
        return JSONResponse({"available": False, "error": err}, status_code=404)
    th = "light" if theme == "light" else "dark"
    if format == "json":
        return report
    if format == "pdf":
        out = Path(_LOG_DIR).parent / "out" / f"note_{sym}.pdf"
        pdf = company_report_pdf(report, out, theme=th)
        if pdf and pdf.exists():
            return FileResponse(str(pdf), media_type="application/pdf", filename=f"note_{sym}.pdf")
        # repli : pas de moteur PDF → on sert le HTML imprimable
    return HTMLResponse(company_report_html(report, theme=th))


_NOTES_DIR = Path(_LOG_DIR).parent / "out" / "notes"


@app.get("/api/notes")
def notes_list() -> dict:
    """Liste les notes d'analyse ARCHIVÉES (pré-générées par le cron) → out/notes/AAAA-MM-JJ/.
    Renvoie {dates:[...], notes:[{date, symbol, html, pdf}]} (récent d'abord)."""
    out: list[dict] = []
    try:
        if _NOTES_DIR.exists():
            for day in sorted(_NOTES_DIR.iterdir(), reverse=True):
                if not day.is_dir():
                    continue
                syms: dict[str, dict] = {}
                for fp in day.glob("note_*.*"):
                    if fp.suffix not in (".html", ".pdf"):
                        continue
                    sym = fp.stem.replace("note_", "")
                    syms.setdefault(sym, {"date": day.name, "symbol": sym})
                    syms[sym][fp.suffix[1:]] = f"/api/note_file?date={day.name}&symbol={sym}&ext={fp.suffix[1:]}"
                out.extend(syms.values())
    except Exception:  # noqa: BLE001
        pass
    dates = sorted({n["date"] for n in out}, reverse=True)
    return {"available": bool(out), "dates": dates, "notes": out}


@app.get("/api/note_file")
def note_file(date: str, symbol: str, ext: str = "html") -> Any:
    """Sert une note archivée (validation stricte du chemin sous out/notes — anti-traversal)."""
    from fastapi.responses import FileResponse, HTMLResponse
    safe_date = "".join(c for c in date if c.isdigit() or c == "-")
    safe_sym = "".join(c for c in symbol.upper() if c.isalnum() or c in ".-")
    ext = "pdf" if ext == "pdf" else "html"
    fp = (_NOTES_DIR / safe_date / f"note_{safe_sym}.{ext}").resolve()
    if not str(fp).startswith(str(_NOTES_DIR.resolve())) or not fp.exists():
        return JSONResponse({"error": "note introuvable"}, status_code=404)
    if ext == "pdf":
        return FileResponse(str(fp), media_type="application/pdf", filename=f"note_{safe_sym}.pdf")
    return HTMLResponse(fp.read_text(encoding="utf-8"))


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
