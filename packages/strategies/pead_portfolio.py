"""PEAD en PORTEFEUILLE quotidien — net de coûts, prêt pour DSR/PBO.

L'event-study répond « le motif existe ? » ; ce module répond « gagne-t-on de l'argent
NET ? ». On construit un portefeuille équipondéré : chaque jour on détient les titres
en fenêtre post-résultats, position = signe(gap de réaction), et on impute le coût
aller-retour à l'ouverture de chaque position. Sortie = série de rendements QUOTIDIENS
(axe-temps commun) → directement consommable par le Sharpe déflaté et le CSCV. numpy.
"""

from __future__ import annotations

from datetime import date

import numpy as np

from packages.portfolio.psr import deflated_sharpe_ratio


def _bar_date(b) -> date:
    ts = getattr(b, "ts", None)
    return ts.date() if hasattr(ts, "date") else ts


def pead_daily_returns(data: dict, earnings: dict, hold: int = 21, entry_lag: int = 1,
                       min_gap: float = 0.0, cost_bps: float = 10.0):
    """Rendements QUOTIDIENS du portefeuille PEAD équipondéré, net de coûts.

    `data`={sym: bars(.ts,.close)}, `earnings`={sym: [dates]}. Coût aller-retour
    (`cost_bps`) imputé sur la 1re barre de détention de chaque position → PnL net par
    trade = somme(rdts) − coût. Renvoie (dates triées, np.array rendements) sur l'union.
    """
    cost = cost_bps / 1e4
    contrib: dict[date, list[float]] = {}
    for sym, bars in data.items():
        eds = earnings.get(sym) or []
        if not bars or not eds:
            continue
        closes = [float(b.close) for b in bars]
        dates = [_bar_date(b) for b in bars]
        n = len(closes)
        for ed in eds:
            d = ed.date() if hasattr(ed, "date") else ed
            i = next((k for k, x in enumerate(dates) if x >= d), None)
            if i is None or i < 1:
                continue
            entry, exit_ = i + entry_lag, i + entry_lag + hold
            if exit_ >= n or closes[i - 1] <= 0 or closes[entry] <= 0:
                continue
            gap = closes[i] / closes[i - 1] - 1.0
            if abs(gap) < min_gap:
                continue
            direction = 1.0 if gap > 0 else -1.0
            for k in range(entry + 1, exit_ + 1):
                if closes[k - 1] <= 0:
                    continue
                r = direction * (closes[k] / closes[k - 1] - 1.0)
                if k == entry + 1:
                    r -= cost                       # coût aller-retour sur ce trade
                contrib.setdefault(dates[k], []).append(r)
    if not contrib:
        return [], np.array([])
    days = sorted(contrib)
    rets = np.array([float(np.mean(contrib[d])) for d in days])
    return days, rets


def _moments(r: np.ndarray) -> tuple[float, float]:
    """(skew, kurtosis) empiriques. (0, 3) si écart-type nul."""
    s = float(r.std())
    if s <= 0:
        return 0.0, 3.0
    m = float(r.mean())
    return float(((r - m) ** 3).mean() / s**3), float(((r - m) ** 4).mean() / s**4)


def pead_metrics(daily_rets, n_trials: int = 1, ppy: int = 252) -> dict:
    """Métriques net-de-coûts + Sharpe déflaté. `n_trials` = essais (déflation)."""
    r = np.asarray(daily_rets, dtype=float)
    n = int(r.size)
    if n < 20:
        return {"available": False, "n": n}
    mean, sd = float(r.mean()), float(r.std(ddof=1))
    sharpe_d = mean / sd if sd > 0 else 0.0
    skew, kurt = _moments(r)
    dsr = deflated_sharpe_ratio(sharpe_d, n, max(1, n_trials), skew, kurt)
    return {"available": True, "n": n, "mean_daily": round(mean, 6),
            "sharpe_daily": round(sharpe_d, 4),
            "sharpe_ann": round(sharpe_d * np.sqrt(ppy), 3),
            "ann_return": round(mean * ppy, 4),
            "win_rate": round(float((r > 0).mean()), 4),
            "n_trials": int(max(1, n_trials)), "dsr": round(float(dsr), 4)}
