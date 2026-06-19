"""Cœur MOMENTUM SECTORIEL (rotation) — rester investi dans les secteurs les plus forts.

À chaque rebalancement (mensuel par défaut), on classe les secteurs par momentum 6 mois (126 j)
et on garde les `top_sectors` meilleurs. Dans ces secteurs, on équipondère les SOCIÉTÉS dont le
cours est au-dessus de leur MM50 (filtre de tendance) → on évite les contre-tendances. Point-in-
time, numpy pur. Rotation : un secteur qui sort/entre du classement est pris en compte.

But : variante ROBUSTE du « prendre le secteur n°1 chaque semaine » (trop concentré/whippy) →
formation 6 mois, rebalancement mensuel, 2 secteurs, filtre tendance. À comparer à QQQ par sweep.
"""

from __future__ import annotations

import numpy as np

from packages.backtest.conviction_backtest import _stats


def sector_momentum_equity_daily(data: dict, sectors: dict, asset_classes: dict | None = None,
                                 top_sectors: int = 2, lookback: int = 126, step: int = 21,
                                 init_cap: float = 10000.0, trend_filter: bool = True,
                                 min_per_sector: int = 2) -> dict:
    """Renvoie {available, equity, dates, current_sectors, current_holdings, weighting}."""
    ac = asset_classes or {}
    syms = [s for s, b in data.items()
            if b and len(b) > lookback + 2 * step and ac.get(s, "equity") in ("equity", "")
            and sectors.get(s)]
    if len(syms) < 5:
        return {"available": False}
    # courbe longue (écarte les IPO récentes) → fenêtre commune profonde, comme le preset
    lmax = max(len(data[s]) for s in syms)
    syms = [s for s in syms if len(data[s]) >= 0.6 * lmax] or syms
    L = min(len(data[s]) for s in syms)
    closes = {s: np.asarray([b.close for b in data[s]][-L:], float) for s in syms}
    ref = max(syms, key=lambda s: len(data[s]))
    dts = [b.ts.isoformat() for b in data[ref]][-L:]
    ma50 = {s: _sma(closes[s], 50) for s in syms}
    by_sector: dict[str, list[str]] = {}
    for s in syms:
        by_sector.setdefault(sectors[s], []).append(s)
    by_sector = {k: v for k, v in by_sector.items() if len(v) >= min_per_sector}
    if len(by_sector) < top_sectors:
        return {"available": False}

    start = max(lookback, 50)
    cur_secs: list[str] = []
    holds: list[str] = []
    eq = [init_cap]
    out_dates = [dts[start]]
    for t in range(start, L - 1):
        if (t - start) % step == 0:                       # rebalancement (rotation sectorielle)
            mom = {}
            for sec, members in by_sector.items():
                rs = [closes[s][t] / closes[s][t - lookback] - 1 for s in members if closes[s][t - lookback] > 0]
                if rs:
                    mom[sec] = float(np.mean(rs))
            cur_secs = sorted(mom, key=lambda k: mom[k], reverse=True)[:top_sectors]
            holds = []
            for sec in cur_secs:
                for s in by_sector[sec]:
                    if (not trend_filter) or closes[s][t] > ma50[s][t]:    # au-dessus de la MM50
                        holds.append(s)
            if not holds:                                  # aucun titre en tendance → tout le top secteur
                holds = [s for sec in cur_secs for s in by_sector[sec]]
        r_d = float(np.mean([closes[s][t + 1] / closes[s][t] - 1 for s in holds])) if holds else 0.0
        eq.append(eq[-1] * (1 + r_d))
        out_dates.append(dts[t + 1])
    if len(eq) < 30:
        return {"available": False}
    return {"available": True, "equity": [round(x, 2) for x in eq], "dates": out_dates,
            "stats": _stats([eq[i + 1] / eq[i] - 1 for i in range(len(eq) - 1)], 252.0),
            "current_sectors": cur_secs, "current_holdings": holds, "weighting": "equal"}


def _sma(x: np.ndarray, w: int) -> np.ndarray:
    """Moyenne mobile simple alignée (les `w-1` premiers points = première moyenne dispo)."""
    if x.size < w:
        return np.full(x.size, x.mean())
    c = np.cumsum(np.insert(x, 0, 0.0))
    out = (c[w:] - c[:-w]) / w
    return np.concatenate([np.full(w - 1, out[0]), out])
