"""Backtest POINT-IN-TIME de la note de conviction (technique) vs univers équipondéré.

Best practice anti-fuite : à chaque rebalancement t, les poids sont calculés **uniquement avec
les données ≤ t** (momentum, tendance vs MM50, faible volatilité, z-scorés en cross-section),
puis les rendements sont réalisés **après** (t → t+step). On compare au buy & hold équipondéré.
Métriques : rendement, Sharpe, **Sharpe déflaté** (essais multiples), max drawdown, turnover.
Numpy pur, gratuit, testable.
"""

from __future__ import annotations

import numpy as np

from packages.portfolio.psr import deflated_sharpe_ratio, probabilistic_sharpe_ratio


def _stats(period_rets: list[float], per_year: float, n_trials: int = 15) -> dict:
    r = np.asarray(period_rets, dtype=float)
    if r.size < 3:
        return {"available": False}
    eq = np.cumprod(1 + r)
    total = float(eq[-1] - 1)
    ann = float((1 + total) ** (per_year / r.size) - 1) if total > -1 else -1.0
    sd = float(r.std())
    sharpe = float(r.mean() / sd * np.sqrt(per_year)) if sd > 0 else 0.0
    peak = np.maximum.accumulate(eq)
    mdd = float((eq / peak - 1).min())
    sr_period = float(r.mean() / sd) if sd > 0 else 0.0      # Sharpe par période (pour PSR/DSR)
    return {"available": True, "total_return": round(total, 4), "annualized": round(ann, 4),
            "sharpe": round(sharpe, 2), "max_drawdown": round(mdd, 4),
            "psr": probabilistic_sharpe_ratio(sr_period, r.size),
            "dsr": deflated_sharpe_ratio(sr_period, r.size, n_trials=n_trials)}


def conviction_backtest(data: dict, step: int = 21, top_n: int = 15, lookback: int = 63,
                        max_weight: float = 0.20) -> dict:
    """Compare une allocation pilotée par conviction (point-in-time) au buy & hold équipondéré."""
    syms = [s for s, b in data.items() if b and len(b) > lookback + 2 * step]
    if len(syms) < 5:
        return {"available": False}
    L = min(len(data[s]) for s in syms)
    M = np.array([[b.close for b in data[s]][-L:] for s in syms], dtype=float)   # actifs × temps
    rets = M[:, 1:] / M[:, :-1] - 1

    def z(x):
        s = x.std()
        return (x - x.mean()) / (s if s else 1.0)

    port, bench = [], []
    prev_w = np.zeros(len(syms))
    turnover = 0.0
    rebs = 0
    for t in range(max(lookback, 50), L - 1, step):
        mom = M[:, t] / M[:, t - lookback] - 1
        sma = M[:, t - 50:t + 1].mean(axis=1)
        trend = M[:, t] / sma - 1
        vol = rets[:, max(0, t - 63):t].std(axis=1) + 1e-9
        conv = (z(mom) + z(trend) - z(vol)) / 3.0                 # faible vol = bonus
        idx = np.argsort(conv)[::-1][:top_n]
        cv = np.clip(conv[idx], 0, None) / vol[idx]              # conviction × inverse-vol
        if cv.sum() <= 0:
            continue
        w = np.zeros(len(syms))
        w[idx] = cv / cv.sum()
        w = np.minimum(w, max_weight)
        w = w / (w.sum() or 1.0)
        nxt = min(t + step, L - 1)
        fwd = M[:, nxt] / M[:, t] - 1                            # rendement RÉALISÉ après t
        port.append(float((w * fwd).sum()))
        bench.append(float(fwd.mean()))
        turnover += float(np.abs(w - prev_w).sum())
        prev_w = w
        rebs += 1
    if rebs < 3:
        return {"available": False}
    per_year = 252.0 / step
    strat = _stats(port, per_year)
    base = _stats(bench, per_year)
    return {"available": True, "strategy": strat, "benchmark": base,
            "n_rebalances": rebs, "step_days": step,
            "turnover_annual": round(turnover / rebs * per_year, 2),
            "alpha": round((strat.get("annualized", 0) - base.get("annualized", 0)), 4)}


def multi_lens_backtest(data: dict, lenses: dict, step: int = 21, top_n: int = 10,
                        lookback: int = 63) -> dict:
    """Compare, pour chaque LENTILLE (Fondamentaux / Investisseurs / ML / Toutes catégories),
    la performance d'un panier ÉQUIPONDÉRÉ de ses top-N symboles, rejoué sur l'historique
    (même grille de rebalancement, rendements réalisés).

    NB honnêteté : la sélection utilise les scores du snapshot courant (panier figé). Pour les
    lentilles fondamentales/investisseurs (neutres vis-à-vis des prix) c'est sans fuite ; pour
    les lentilles momentum/ML, cela encode le momentum récent → à lire comme INDICATIF.
    """
    syms_all = [s for s, b in data.items() if b and len(b) > lookback + 2 * step]
    if len(syms_all) < 5:
        return {"available": False}
    L = min(len(data[s]) for s in syms_all)
    closes = {s: [b.close for b in data[s]][-L:] for s in syms_all}
    per_year = 252.0 / step
    out: dict[str, dict] = {}
    for lens, scores in lenses.items():
        ranked = sorted((s for s in syms_all if scores.get(s) is not None),
                        key=lambda s: scores[s], reverse=True)[:top_n]
        if len(ranked) < 3:
            continue
        M = np.array([closes[s] for s in ranked], dtype=float)
        port = []
        for t in range(max(lookback, 50), L - 1, step):
            nxt = min(t + step, L - 1)
            port.append(float((M[:, nxt] / M[:, t] - 1).mean()))     # panier équipondéré
        st = _stats(port, per_year)
        if st.get("available"):
            st["names"] = ranked
            out[lens] = st
    return {"available": bool(out), "lenses": out, "top_n": top_n, "step_days": step}
