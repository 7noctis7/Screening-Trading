"""Santé & couverture des données — contrôle qualité point-in-time (best practice data eng).

Sur les séries OHLCV chargées (réelles ou synthétiques) :
- **qualité** : NaN/valeurs ≤ 0, sauts aberrants (outliers), fraîcheur (staleness), historique court ;
- **couverture** : par classe d'actifs, part de séries « complètes » (≥ 250 barres) + barres moyennes.
Aucune dépendance (stdlib), testable hors-ligne.
"""

from __future__ import annotations

from datetime import datetime, timezone

_MIN_BARS = 250                        # ~1 an de daily = série exploitable
_OUTLIER = 0.40                        # variation intraday > 40 % = suspecte


def _closes(bars) -> list[float]:
    out = []
    for b in bars:
        c = getattr(b, "close", None) if not isinstance(b, dict) else b.get("c")
        out.append(c)
    return out


def series_health(symbol: str, bars, now: datetime | None = None) -> dict:
    """Rapport qualité d'une série : NaN, outliers, fraîcheur, longueur."""
    now = now or datetime.now(timezone.utc)
    closes = _closes(bars)
    n = len(closes)
    n_bad = sum(1 for c in closes if c is None or (isinstance(c, (int, float)) and c <= 0))
    outliers = 0
    for a, b in zip(closes[:-1], closes[1:]):
        if a and b and a > 0 and abs(b / a - 1.0) > _OUTLIER:
            outliers += 1
    last = bars[-1] if bars else None
    last_ts = getattr(last, "ts", None) if last is not None and not isinstance(last, dict) else None
    stale_days = None
    if isinstance(last_ts, datetime):
        stale_days = (now - last_ts).days
    return {"symbol": symbol, "n_bars": n, "n_bad": n_bad, "outliers": outliers,
            "stale_days": stale_days, "complete": n >= _MIN_BARS and n_bad == 0}


def health_report(data: dict, acmap: dict[str, str], now: datetime | None = None) -> dict:
    """Rapport global : score qualité 0-100 + couverture par classe d'actifs."""
    rows = [series_health(s, b, now) for s, b in data.items()]
    n = len(rows) or 1
    complete = sum(1 for r in rows if r["complete"])
    bad = sum(r["n_bad"] for r in rows)
    outliers = sum(r["outliers"] for r in rows)
    short = sum(1 for r in rows if r["n_bars"] < _MIN_BARS)
    # score : pénalise séries incomplètes, NaN, outliers
    score = 100.0
    score -= (1 - complete / n) * 40
    score -= min(30, bad)
    score -= min(15, outliers * 0.5)
    score -= (short / n) * 15
    score = max(0.0, round(score, 1))
    # couverture par classe
    cov: dict[str, dict] = {}
    for r in rows:
        ac = acmap.get(r["symbol"], "equity")
        c = cov.setdefault(ac, {"asset_class": ac, "n": 0, "complete": 0, "bars": 0})
        c["n"] += 1
        c["complete"] += int(r["complete"])
        c["bars"] += r["n_bars"]
    coverage = []
    for ac, c in sorted(cov.items()):
        coverage.append({"asset_class": ac, "n": c["n"], "complete": c["complete"],
                         "complete_pct": round(c["complete"] / c["n"], 3) if c["n"] else 0.0,
                         "avg_bars": round(c["bars"] / c["n"]) if c["n"] else 0})
    worst = sorted([r for r in rows if not r["complete"]],
                   key=lambda r: (r["n_bars"], -r["n_bad"]))[:8]
    return {"score": score, "n_series": len(rows), "complete": complete,
            "n_bad": bad, "outliers": outliers, "short": short,
            "coverage": coverage, "worst": worst, "min_bars": _MIN_BARS}
