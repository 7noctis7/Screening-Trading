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
