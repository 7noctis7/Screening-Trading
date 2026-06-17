"""Stratégie EARNINGS / PEAD (Post-Earnings Announcement Drift) — event study, gratuit.

Anomalie documentée (Bernard & Thomas 1989) : après un résultat, le cours **dérive** dans le
sens de la surprise pendant plusieurs semaines. Proxy GRATUIT de la surprise = le **gap de
réaction** (close du jour des résultats vs close précédent) — pas besoin de données BPA payantes.

Règles (event study) :
  - réaction = close[J] / close[J-1] − 1 ;  direction = signe(réaction) ;
  - entrée à J+entry_lag (close), sortie à J+hold (par défaut J+21) → on capte le DRIFT ;
  - on évite le risque binaire du jour J (entrée APRÈS l'annonce).
Renvoie le rendement par événement + métriques (moyenne, t-stat, win rate) vs marché sur la même
fenêtre. stdlib/numpy, testable hors-ligne.
"""

from __future__ import annotations

import numpy as np


def _bisect_ge(dates: list, d) -> int | None:
    """Premier index dont la date ≥ d (gère week-ends/jours fériés). None si hors série."""
    lo, hi = 0, len(dates)
    while lo < hi:
        mid = (lo + hi) // 2
        if dates[mid] < d:
            lo = mid + 1
        else:
            hi = mid
    return lo if lo < len(dates) else None


def pead_backtest(data: dict, earnings: dict, hold: int = 21, entry_lag: int = 1,
                  min_gap: float = 0.0) -> dict:
    """Backtest PEAD event-study. `data`: {sym: bars(.ts,.close)} ; `earnings`: {sym: [dates]}."""
    ev_ret, mkt_ret, gaps = [], [], []
    for sym, bars in data.items():
        eds = earnings.get(sym) or []
        if not bars or not eds:
            continue
        closes = [b.close for b in bars]
        dates = [b.ts.date() if hasattr(b.ts, "date") else b.ts for b in bars]
        for ed in eds:
            d = ed.date() if hasattr(ed, "date") else ed
            i = _bisect_ge(dates, d)
            if i is None or i < 1:
                continue
            entry, ex = i + entry_lag, i + entry_lag + hold
            if ex >= len(closes) or closes[i - 1] <= 0 or closes[entry] <= 0:
                continue
            gap = closes[i] / closes[i - 1] - 1
            if abs(gap) < min_gap:
                continue
            direction = 1.0 if gap > 0 else -1.0
            ev_ret.append(direction * (closes[ex] / closes[entry] - 1))     # PEAD (suivi du drift)
            mkt_ret.append(closes[ex] / closes[entry] - 1)                  # marché (long passif)
            gaps.append(gap)
    n = len(ev_ret)
    if n < 20:
        return {"available": False, "n_events": n}
    a = np.asarray(ev_ret)
    mean, sd = float(a.mean()), float(a.std())
    return {
        "available": True, "n_events": n, "hold_days": hold,
        "mean_return": round(mean, 4), "median_return": round(float(np.median(a)), 4),
        "win_rate": round(float((a > 0).mean()), 4),
        "t_stat": round(mean / sd * np.sqrt(n), 2) if sd else 0.0,
        "sharpe_per_trade": round(mean / sd, 3) if sd else 0.0,
        "market_mean_return": round(float(np.mean(mkt_ret)), 4),   # même fenêtre, long passif
        "edge_vs_market": round(mean - float(np.mean(mkt_ret)), 4),
        "avg_gap": round(float(np.mean(np.abs(gaps))), 4),
    }
