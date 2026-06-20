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
        v = float(x)
        return None if v != v else v          # écarte les NaN (pandas) → None propre
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


def _yf_earnings(symbols: list[str], days_back: int = 21, days_fwd: int = 120) -> list[dict]:
    """Repli yfinance CORRECT : chaque DATE a son propre BPA estimé/réel (réel = None tant que non
    publié → pas de surprise factice sur les rapports à venir). Revenu estimé (prochain trimestre)
    via `calendar` ; revenu réel (dernier trimestre publié) via les comptes trimestriels (best-effort)."""
    try:
        import yfinance as yf
    except Exception:  # noqa: BLE001
        return []
    today = datetime.now(timezone.utc).date()
    lo, hi = (today - timedelta(days=days_back)), (today + timedelta(days=days_fwd))
    out: list[dict] = []
    for s in symbols[:80]:                                  # borne : appels réseau par actif (top scores en tête)
        try:
            t = yf.Ticker(s)
            # revenu ESTIMÉ du prochain trimestre + sa date (via calendar)
            rev_est, next_date = None, None
            try:
                cal = dict(t.calendar) if getattr(t, "calendar", None) is not None else {}
                rev_est = _num(cal.get("Revenue Average"))
                dd = cal.get("Earnings Date") or cal.get("Earnings Dates")
                d0 = dd[0] if isinstance(dd, (list, tuple)) and dd else dd
                next_date = d0.isoformat()[:10] if hasattr(d0, "isoformat") else (str(d0)[:10] if d0 else None)
            except Exception:  # noqa: BLE001
                pass
            # revenu RÉEL du dernier trimestre publié (comptes trimestriels)
            rev_act, rev_act_date = None, None
            try:
                qf = getattr(t, "quarterly_income_stmt", None)
                if qf is not None and "Total Revenue" in qf.index and len(qf.columns):
                    rev_act = _num(qf.loc["Total Revenue", qf.columns[0]])
                    rev_act_date = qf.columns[0].date() if hasattr(qf.columns[0], "date") else None
            except Exception:  # noqa: BLE001
                pass
            # liste des DATES avec BPA estimé/réel (réel correct par date) via get_earnings_dates
            ed = t.get_earnings_dates(limit=12)
            if ed is None or not len(ed):
                continue
            recent_past = None
            for ts, row in ed.iterrows():
                d = ts.date() if hasattr(ts, "date") else None
                if d is None or d < lo or d > hi:
                    continue
                ds = d.isoformat()
                upcoming = d >= today
                ev = {"symbol": s.upper(), "date": ds, "when": "",
                      "eps_estimate": _num(row.get("EPS Estimate")),
                      "eps_actual": None if upcoming else _num(row.get("Reported EPS")),
                      "revenue_estimate": rev_est if (next_date and ds == next_date) else None,
                      "revenue_actual": None, "source": "yfinance"}
                out.append(ev)
                if not upcoming and (recent_past is None or ds > recent_past["date"]):
                    recent_past = ev
            # rattache le revenu réel connu au trimestre publié le plus récent (approximation honnête)
            if recent_past is not None and rev_act is not None:
                if rev_act_date is None or abs((rev_act_date - today).days) < 130:
                    recent_past["revenue_actual"] = rev_act
        except Exception:  # noqa: BLE001
            continue
    return out


def earnings_for(symbols: list[str], days_back: int = 21, days_fwd: int = 120) -> list[dict]:
    """Prochains résultats des `symbols` (actions). FMP si clé+plan, sinon yfinance. Triés par date
    croissante ; les rapports déjà publiés (avec réel) restent visibles sur `days_back` jours."""
    syms = [str(s).upper() for s in symbols if s]
    sset = set(syms)
    rows = _fmp_earnings(sset, days_back, days_fwd)
    if not rows:                                            # repli yfinance (sans clé / plan FMP limité)
        rows = _yf_earnings(syms, days_back, days_fwd)
    today = datetime.now(timezone.utc).date().isoformat()
    rows = [r for r in rows if r.get("date")]
    rows.sort(key=lambda r: (r["date"] < today, r["date"]))  # à venir d'abord, puis récents
    return rows
