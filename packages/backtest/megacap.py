"""Rotation MÉGA-CAPS : détenir les N plus grosses sociétés, rééquilibrées quand le classement
change. Proxy de « taille » = dollar-volume moyen récent (prix × volume) — disponible dans l'OHLCV,
contrairement à la capitalisation historique (souvent indisponible). Re-classé à chaque période →
les entrées/sorties suivent les changements de classement. Équipondéré, point-in-time. numpy pur.
"""

from __future__ import annotations

import numpy as np

from packages.backtest.conviction_backtest import _stats


def megacap_rotation(data: dict, asset_classes: dict | None = None, top_n: int = 10,
                     step: int = 63, lookback: int = 63) -> dict:
    """Top-N par dollar-volume, rééquilibré tous les `step` jours (rotation sur le classement)."""
    ac = asset_classes or {}
    syms = [s for s, b in data.items()
            if b and len(b) > lookback + 2 * step and ac.get(s, "equity") in ("equity", "etf")]
    if len(syms) < top_n:
        return {"available": False}
    L = min(len(data[s]) for s in syms)
    closes = {s: np.asarray([b.close for b in data[s]][-L:], float) for s in syms}
    dvol = {s: closes[s] * np.asarray([getattr(b, "volume", 0.0) for b in data[s]][-L:], float)
            for s in syms}
    port, prev, turn, rebs = [], set(), 0.0, 0
    last_top: list[str] = []
    for t in range(max(lookback, 50), L - 1, step):
        score = {s: float(np.mean(dvol[s][max(0, t - lookback):t])) for s in syms}
        top = sorted(score, key=lambda s: score[s], reverse=True)[:top_n]
        nxt = min(t + step, L - 1)
        port.append(float(np.mean([closes[s][nxt] / closes[s][t] - 1 for s in top])))
        turn += len(set(top) ^ prev) / (2 * top_n)
        prev, last_top, rebs = set(top), top, rebs + 1
    if rebs < 3:
        return {"available": False}
    per_year = 252.0 / step
    return {"available": True, "stats": _stats(port, per_year), "n_rebalances": rebs,
            "step_days": step, "top_n": top_n,
            "turnover_per_rebal": round(turn / rebs, 2), "current_top": last_top}


def megacap_equity_daily(data: dict, asset_classes: dict | None = None, top_n: int = 10,
                         step: int = 63, lookback: int = 63, init_cap: float = 10000.0,
                         include_etf: bool = False) -> dict:
    """Courbe d'equity QUOTIDIENNE de la rotation top-N méga-caps (équipondéré, re-classé tous
    les `step` jours par dollar-volume) → utilisable comme « cœur » mélangé au preset. Par défaut
    SOCIÉTÉS uniquement (les ETF type SPY/QQQ sont exclus). Renvoie {available, equity, dates,
    current_top}. Anti-fuite : on détient le panier classé EN t pour le rendement t→t+1."""
    ac = asset_classes or {}
    _ok = ("equity", "etf") if include_etf else ("equity", "")
    syms = [s for s, b in data.items()
            if b and len(b) > lookback + 2 * step and ac.get(s, "equity") in _ok]
    if len(syms) < top_n:
        return {"available": False}
    L = min(len(data[s]) for s in syms)
    closes = {s: np.asarray([b.close for b in data[s]][-L:], float) for s in syms}
    dvol = {s: closes[s] * np.asarray([getattr(b, "volume", 0.0) for b in data[s]][-L:], float)
            for s in syms}
    ref = max(syms, key=lambda s: len(data[s]))
    dts = [b.ts.isoformat() for b in data[ref]][-L:]
    start = max(lookback, 50)
    cur: list[str] = []
    eq = [init_cap]
    out_dates = [dts[start]]
    for t in range(start, L - 1):
        if (t - start) % step == 0:                       # re-classement (rotation)
            score = {s: float(np.mean(dvol[s][max(0, t - lookback):t])) for s in syms}
            cur = sorted(score, key=lambda s: score[s], reverse=True)[:top_n]
        r_d = float(np.mean([closes[s][t + 1] / closes[s][t] - 1 for s in cur])) if cur else 0.0
        eq.append(eq[-1] * (1 + r_d))
        out_dates.append(dts[t + 1])
    if len(eq) < 30:
        return {"available": False}
    return {"available": True, "equity": [round(x, 2) for x in eq], "dates": out_dates,
            "current_top": cur}
