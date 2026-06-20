"""Génération AUTOMATIQUE des cônes de risque (VaR/EVT) → overlay store.

Découplage strict : ce module LIT les données du cœur **via l'API HTTP** (jamais d'import du cœur),
calcule un cône de VaR à partir des prix RÉELS, et ÉCRIT dans l'OverlayStore. Le front affiche alors
le cône sans intervention manuelle de l'agent.

Le calcul `var_cone` est PUR (numpy facultatif, repli stdlib) → testable hors-ligne.
POINT-IN-TIME : volatilité estimée sur fenêtre TRAILING uniquement (aucune donnée future).
"""

from __future__ import annotations

import json
import math
import urllib.request
from typing import Any

from packages.mcp_tradingview.models import BlackoutZone, ChartMarker, RiskBand
from packages.mcp_tradingview.store import OverlayStore

# z-scores usuels : VaR 95 % ≈ 1.645 ; VaR 99 % ≈ 2.326
Z_VAR95 = 1.645
Z_VAR99 = 2.326


def _rolling_std(rets: list[float], lookback: int) -> list[float | None]:
    """Écart-type glissant (échantillon) TRAILING — None tant que la fenêtre n'est pas pleine."""
    out: list[float | None] = []
    for i in range(len(rets)):
        if i + 1 < lookback:
            out.append(None)
            continue
        win = rets[i + 1 - lookback : i + 1]
        m = sum(win) / len(win)
        var = sum((x - m) ** 2 for x in win) / (len(win) - 1) if len(win) > 1 else 0.0
        out.append(math.sqrt(var))
    return out


def var_cone(times: list[str], closes: list[float], z: float = Z_VAR95,
             lookback: int = 21, evt_mult: float = 1.0) -> list[RiskBand]:
    """Enveloppe de VaR autour du prix : bornes = close × (1 ± z·σ_trailing·evt_mult).

    Args:
        times/closes : séries alignées (dates ISO, clôtures réelles).
        z            : quantile (1.645 = VaR95, 2.326 = VaR99).
        lookback     : fenêtre de volatilité (jours).
        evt_mult     : facteur d'élargissement des queues (EVT) — 1.0 = gaussien, >1 = queues épaisses.

    Returns: liste de RiskBand (uniquement là où σ est définie). Borne basse plancher à 0.
    """
    n = min(len(times), len(closes))
    if n < lookback + 2:
        return []
    c = [float(x) for x in closes[:n]]
    rets = [math.log(c[i] / c[i - 1]) for i in range(1, n) if c[i - 1] > 0 and c[i] > 0]
    # rets[i] correspond à la barre i+1 ; on aligne en décalant d'un cran.
    sig = _rolling_std(rets, lookback)
    bands: list[RiskBand] = []
    for j, s in enumerate(sig):
        if s is None:
            continue
        i = j + 1                                       # indice de barre correspondant au retour rets[j]
        if i >= n:
            break
        k = z * s * max(0.1, evt_mult)
        px = c[i]
        bands.append(RiskBand(time=str(times[i])[:10], upper=px * (1 + k), lower=max(0.0, px * (1 - k))))
    return bands


# ─────────────────────────── Lecture API (HTTP, découplé) ───────────────────────────
def _get_json(url: str, timeout: float = 8.0) -> Any:
    with urllib.request.urlopen(url, timeout=timeout) as r:  # noqa: S310 — localhost contrôlé
        return json.loads(r.read().decode())


def _bars_to_series(bars: list[dict]) -> tuple[list[str], list[float]]:
    times = [str(b.get("t", ""))[:10] for b in bars]
    closes = [float(b.get("c", 0) or 0) for b in bars]
    return times, closes


def _blackouts_from_events(events: dict, symbol: str, pad_before: int = 2, pad_after: int = 1) -> list[BlackoutZone]:
    from datetime import date, timedelta
    out: list[BlackoutZone] = []
    for e in (events.get("earnings", []) if isinstance(events, dict) else []):
        if str(e.get("symbol", "")).upper() != symbol.upper() or not e.get("date"):
            continue
        try:
            d = date.fromisoformat(str(e["date"])[:10])
        except ValueError:
            continue
        out.append(BlackoutZone(start=(d - timedelta(days=pad_before)).isoformat(),
                                end=(d + timedelta(days=pad_after)).isoformat(),
                                label=f"résultats {e.get('symbol','')}"))
    return out


def populate_from_api(base_url: str = "http://localhost:8000", store: OverlayStore | None = None,
                      tickers: list[str] | None = None, z: float = Z_VAR95, lookback: int = 21,
                      evt_mult: float = 1.15) -> dict:
    """Calcule et écrit les overlays (cône VaR + marqueurs réels + blackouts résultats) pour les
    symboles détenus (ou `tickers`). Renvoie un résumé. Tolérant : API down → {available: False}."""
    st = store or OverlayStore()
    base = base_url.rstrip("/")
    try:
        pos = _get_json(f"{base}/api/positions")
    except Exception as e:  # noqa: BLE001
        return {"available": False, "error": f"API injoignable: {e}"}
    series = pos.get("series", {}) or {}
    markers_by = pos.get("markers", {}) or {}
    try:
        events = _get_json(f"{base}/api/events")
    except Exception:  # noqa: BLE001
        events = {}
    syms = tickers or [p.get("symbol") for p in pos.get("real_positions", []) if p.get("symbol")] or list(series)
    done: list[str] = []
    for sym in dict.fromkeys(syms):
        bars = series.get(sym)
        if not bars:
            continue
        times, closes = _bars_to_series(bars)
        bands = var_cone(times, closes, z=z, lookback=lookback, evt_mult=evt_mult)
        mks = [ChartMarker(time=str(m.get("t", ""))[:10], side=str(m.get("side", "buy")).lower())
               for m in (markers_by.get(sym) or [])]
        zones = _blackouts_from_events(events, sym)
        from packages.mcp_tradingview.models import Overlay
        st.set_overlay(Overlay(ticker=sym, markers=mks, bands=bands, blackouts=zones, source="risk-auto"))
        done.append(sym)
    return {"available": True, "tickers": done, "n": len(done),
            "var_z": z, "lookback": lookback, "evt_mult": evt_mult}


def populate_from_snapshot(store: OverlayStore | None = None, z: float = Z_VAR95,
                           lookback: int = 21, evt_mult: float = 1.15) -> dict:
    """Variante OFFLINE (cron) : construit le snapshot directement (pas d'API à démarrer) et écrit
    les overlays. Import du cœur PARESSEUX (sens autorisé : connecteur → cœur). Tolérant aux pannes."""
    st = store or OverlayStore()
    try:
        from apps.api.snapshot import build_snapshot
        snap = build_snapshot()
    except Exception as e:  # noqa: BLE001
        return {"available": False, "error": f"snapshot indisponible: {e}"}
    dash = snap.get("dashboard", {})
    series = dash.get("chart_series", {}) or {}
    markers_by = dash.get("real_markers", {}) or {}
    held = [p.get("symbol") for p in snap.get("live", {}).get("real", {}).get("positions", [])
            if p.get("symbol")] or list(series)
    # blackouts résultats (best-effort réseau via le module events ; ignoré si indisponible)
    events: dict = {}
    try:
        from packages.events import earnings_for
        events = {"earnings": earnings_for([s for s in dict.fromkeys(held)])}
    except Exception:  # noqa: BLE001
        events = {}
    from packages.mcp_tradingview.models import Overlay
    done: list[str] = []
    for sym in dict.fromkeys(held):
        bars = series.get(sym)
        if not bars:
            continue
        times, closes = _bars_to_series(bars)
        bands = var_cone(times, closes, z=z, lookback=lookback, evt_mult=evt_mult)
        mks = [ChartMarker(time=str(m.get("t", ""))[:10], side=str(m.get("side", "buy")).lower())
               for m in (markers_by.get(sym) or [])]
        zones = _blackouts_from_events(events, sym)
        st.set_overlay(Overlay(ticker=sym, markers=mks, bands=bands, blackouts=zones, source="risk-auto-cron"))
        done.append(sym)
    return {"available": True, "tickers": done, "n": len(done), "mode": "offline"}
