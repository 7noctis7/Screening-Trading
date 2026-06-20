"""Calendrier de RÉSULTATS trimestriels (réel) : date du prochain rapport + BPA (EPS) et REVENU
**estimés** et, s'ils sont publiés, **annoncés (réels)**.

Priorité des sources :
  1. **FMP** (`FMP_API_KEY`) — calendrier structuré : epsEstimated/revenueEstimated + eps/revenue réels.
  2. **yfinance** (repli sans clé) — date + estimations (BPA/revenu moyens) + dernier BPA publié.

Les fonctions de PARSING sont pures (testables hors-ligne) ; la récupération réseau est encapsulée
et tolérante aux pannes (renvoie [] si indisponible)."""

from __future__ import annotations

import json
import os
import urllib.request
from datetime import datetime, timedelta, timezone

_FMP_BASE = "https://financialmodelingprep.com/api/v3"


def _num(x) -> float | None:
    try:
        if x is None or x == "":
            return None
        return float(x)
    except (TypeError, ValueError):
        return None


def parse_fmp_earnings(rows: list[dict], symbols: set[str]) -> list[dict]:
    """Normalise le calendrier FMP (`/v3/earning_calendar`) → liste filtrée sur `symbols`.
    Chaque ligne : {symbol, date, when, eps_estimate, eps_actual, revenue_estimate, revenue_actual}."""
    out: list[dict] = []
    for r in rows or []:
        sym = str(r.get("symbol", "")).upper()
        if symbols and sym not in symbols:
            continue
        out.append({
            "symbol": sym, "date": str(r.get("date", ""))[:10],
            "when": r.get("time", "") or "",
            "eps_estimate": _num(r.get("epsEstimated")), "eps_actual": _num(r.get("eps")),
            "revenue_estimate": _num(r.get("revenueEstimated")), "revenue_actual": _num(r.get("revenue")),
            "source": "FMP",
        })
    return out


def parse_yf_calendar(symbol: str, cal: dict | None, last_eps_actual: float | None = None,
                      last_rev_actual: float | None = None) -> dict | None:
    """Normalise le `Ticker.calendar` yfinance (dict) → 1 événement (prochain rapport) ou None."""
    if not cal:
        return None
    dates = cal.get("Earnings Date") or cal.get("Earnings Dates")
    d = None
    if isinstance(dates, (list, tuple)) and dates:
        d = dates[0]
    elif dates:
        d = dates
    if d is None:
        return None
    try:
        ds = d.isoformat()[:10] if hasattr(d, "isoformat") else str(d)[:10]
    except Exception:  # noqa: BLE001
        ds = str(d)[:10]
    return {
        "symbol": symbol.upper(), "date": ds, "when": "",
        "eps_estimate": _num(cal.get("Earnings Average")),
        "eps_actual": _num(last_eps_actual),
        "revenue_estimate": _num(cal.get("Revenue Average")),
        "revenue_actual": _num(last_rev_actual),
        "source": "yfinance",
    }


def _fmp_earnings(symbols: set[str], days_back: int, days_fwd: int) -> list[dict]:
    key = os.environ.get("FMP_API_KEY", "")
    if not key:
        return []
    today = datetime.now(timezone.utc).date()
    frm = (today - timedelta(days=days_back)).isoformat()
    to = (today + timedelta(days=days_fwd)).isoformat()
    url = f"{_FMP_BASE}/earning_calendar?from={frm}&to={to}&apikey={key}"
    try:
        with urllib.request.urlopen(url, timeout=20) as r:  # noqa: S310 — URL FMP contrôlée
            rows = json.loads(r.read().decode())
        return parse_fmp_earnings(rows if isinstance(rows, list) else [], symbols)
    except Exception:  # noqa: BLE001
        return []


def _yf_earnings(symbols: list[str]) -> list[dict]:
    try:
        import yfinance as yf
    except Exception:  # noqa: BLE001
        return []
    out: list[dict] = []
    for s in symbols[:40]:                                  # borne : appels réseau par actif
        try:
            t = yf.Ticker(s)
            last_eps = None
            try:
                ed = t.get_earnings_dates(limit=8)
                if ed is not None and len(ed):
                    rep = ed["Reported EPS"].dropna() if "Reported EPS" in ed else None
                    if rep is not None and len(rep):
                        last_eps = float(rep.iloc[0])
            except Exception:  # noqa: BLE001
                pass
            ev = parse_yf_calendar(s, dict(t.calendar) if getattr(t, "calendar", None) is not None else None,
                                   last_eps_actual=last_eps)
            if ev and ev.get("date"):
                out.append(ev)
        except Exception:  # noqa: BLE001
            continue
    return out


def earnings_for(symbols: list[str], days_back: int = 21, days_fwd: int = 120) -> list[dict]:
    """Prochains résultats des `symbols` (actions). FMP si clé, sinon yfinance. Triés par date
    croissante ; les rapports déjà publiés (avec réel) restent visibles sur `days_back` jours."""
    syms = [str(s).upper() for s in symbols if s]
    sset = set(syms)
    rows = _fmp_earnings(sset, days_back, days_fwd)
    if not rows:                                            # repli yfinance (sans clé)
        rows = _yf_earnings(syms)
    today = datetime.now(timezone.utc).date().isoformat()
    rows = [r for r in rows if r.get("date")]
    rows.sort(key=lambda r: (r["date"] < today, r["date"]))  # à venir d'abord, puis récents
    return rows
