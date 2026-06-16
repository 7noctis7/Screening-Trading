"""Builders de payloads API — fonctions PURES (JSON-sérialisable), testables offline.

Le front ne contient aucune logique : il consomme ces structures. Toute la dérivation
(totaux, P&L, exposition, contributions de facteurs) est calculée ici puis testée.
"""

from __future__ import annotations

from datetime import datetime

from packages.core.models import Position, RegimeState
from packages.portfolio import metrics as M


def regime_payload(regime: RegimeState, exposure_multiplier: float) -> dict:
    return {
        "as_of": regime.ts.isoformat(),
        "cycle": regime.cycle.value,
        "risk_mode": regime.risk_mode.value,
        "vix": regime.vix,
        "exposure_multiplier": round(exposure_multiplier, 3),
        "extras": {k: _round(v) for k, v in (regime.extras or {}).items()},
    }


def equity_series(equity_curve: list[float], timestamps: list[datetime] | None = None) -> list[dict]:
    if timestamps and len(timestamps) == len(equity_curve):
        return [{"t": ts.isoformat(), "v": round(v, 2)}
                for ts, v in zip(timestamps, equity_curve)]
    return [{"t": i, "v": round(v, 2)} for i, v in enumerate(equity_curve)]


def screener_payload(ranked: list, as_of: datetime) -> dict:
    rows = []
    for i, r in enumerate(ranked, 1):
        rows.append({
            "rank": i,
            "symbol": r.symbol,
            "asset_class": getattr(r, "asset_class", None),
            "score": round(r.score, 4),
            "factors": {k: round(v, 4) for k, v in (r.contributions or {}).items()},
            "reason": getattr(r, "reason", None),
        })
    return {"as_of": as_of.isoformat(), "count": len(rows), "rows": rows}


def composition_payload(positions: list[Position], marks: dict[str, float],
                        meta: dict[str, dict] | None = None) -> dict:
    meta = meta or {}
    rows, invested_tot, value_tot, net = [], 0.0, 0.0, 0.0
    for p in positions:
        mark = marks.get(p.instrument, p.avg_price)
        invested = p.avg_price * p.qty
        value = mark * p.qty
        sign = 1 if p.side.value == "long" else -1
        pnl = (value - invested) * sign
        m = meta.get(p.instrument, {})
        rows.append({
            "symbol": p.instrument, "side": p.side.value,
            "entry_date": m.get("entry_date"), "entry_reason": m.get("entry_reason"),
            "asset_class": m.get("asset_class"), "qty": round(p.qty, 6),
            "avg_price": round(p.avg_price, 4), "invested": round(invested, 2),
            "current_value": round(value, 2),
            "pnl_abs": round(pnl, 2),
            "pnl_pct": round(pnl / invested, 4) if invested else 0.0,
        })
        invested_tot += invested
        value_tot += value
        net += value * sign
    return {
        "rows": rows,
        "totals": {
            "invested": round(invested_tot, 2),
            "current_value": round(value_tot, 2),
            "pnl_abs": round(value_tot - invested_tot, 2),
            "pnl_pct": round((value_tot - invested_tot) / invested_tot, 4) if invested_tot else 0.0,
            "gross_exposure": round(value_tot, 2),
            "net_exposure": round(net, 2),
        },
    }


def metrics_payload(equity_curve: list[float], rets: list[float] | None = None) -> dict:
    s = M.summary(equity_curve, rets or [])
    return {k: round(v, 4) for k, v in s.items()}


def benchmark_comparison(portfolio_equity: list[float],
                         benchmarks: dict[str, list[float]]) -> dict:
    """Courbes rebasées à 100 (portefeuille vs benchmarks) pour superposition."""
    out = {"portfolio": _rebase(portfolio_equity)}
    for name, curve in benchmarks.items():
        out[name] = _rebase(curve)
    return out


def _rebase(curve: list[float]) -> list[float]:
    if not curve or curve[0] == 0:
        return [round(v, 2) for v in curve]
    base = curve[0]
    return [round(v / base * 100, 2) for v in curve]


def trade_payload(tr) -> dict:
    """TradeRecord → dict JSON-safe (dates isoformat, enums .value)."""
    def conv(v):
        if isinstance(v, datetime):
            return v.isoformat()
        if hasattr(v, "value"):          # Enum
            return v.value
        if isinstance(v, float):
            return round(v, 4)
        return v
    from dataclasses import fields
    return {f.name: conv(getattr(tr, f.name)) for f in fields(tr)}


def _round(v):
    return round(v, 4) if isinstance(v, (int, float)) else v


def correlation_payload(symbols: list[str], matrix, clusters: list[list[str]]) -> dict:
    return {"symbols": symbols,
            "matrix": [[round(float(v), 3) for v in row] for row in matrix],
            "clusters": clusters}


def review_payload(review) -> dict:
    return {"health_score": review.health_score, "strengths": review.strengths,
            "weaknesses": review.weaknesses, "risks": review.risks,
            "recommendations": review.recommendations, "disclaimer": review.disclaimer}
