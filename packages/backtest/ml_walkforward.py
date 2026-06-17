"""Backtest walk-forward avec ML POINT-IN-TIME (gratuit, sans fuite du futur).

À chaque date de rebalancement t :
  1. on entraîne un modèle (logit) UNIQUEMENT sur des labels déjà réalisés (fenêtre se terminant ≤ t) ;
  2. on prédit la proba de hausse à t (features calculées avec données ≤ t) ;
  3. on fusionne avec une conviction technique (momentum/tendance/faible-vol, point-in-time) ;
  4. on alloue (conviction × inverse-vol, plafonnée) et on réalise les rendements t → t+step.

On compare : **conviction+ML** vs **conviction technique seule** vs **équipondéré**.
Lourd (ré-entraînement) → à lancer en script, pas dans l'API. Numpy + LogitModel (gratuit).
"""

from __future__ import annotations

import numpy as np

from packages.ml.model import LogitModel
from packages.portfolio.psr import deflated_sharpe_ratio


def _features(M: np.ndarray, rets: np.ndarray, u: int) -> np.ndarray:
    """Features cross-section à l'instant u (1 ligne/actif), avec données ≤ u uniquement."""
    mom1 = M[:, u] / M[:, u - 21] - 1
    mom3 = M[:, u] / M[:, u - 63] - 1
    sma50 = M[:, u - 50:u + 1].mean(axis=1)
    trend = M[:, u] / sma50 - 1
    win = rets[:, max(0, u - 63):u]
    vol = win.std(axis=1) + 1e-9
    # RSI 14 approx
    d = rets[:, u - 14:u]
    up = np.where(d > 0, d, 0).mean(axis=1)
    dn = -np.where(d < 0, d, 0).mean(axis=1) + 1e-9
    rsi = 100 - 100 / (1 + up / dn)
    return np.column_stack([mom1, mom3, trend, rsi / 100.0, vol])


def _z(x: np.ndarray) -> np.ndarray:
    s = x.std()
    return (x - x.mean()) / (s if s else 1.0)


def _metrics(period_rets: list[float], per_year: float, n_trials: int) -> dict:
    r = np.asarray(period_rets, dtype=float)
    if r.size < 3:
        return {"available": False}
    eq = np.cumprod(1 + r)
    total = float(eq[-1] - 1)
    sd = float(r.std())
    sharpe = float(r.mean() / sd * np.sqrt(per_year)) if sd > 0 else 0.0
    mdd = float((eq / np.maximum.accumulate(eq) - 1).min())
    sr_p = float(r.mean() / sd) if sd > 0 else 0.0
    return {"available": True, "total_return": round(total, 4),
            "annualized": round((1 + total) ** (per_year / r.size) - 1, 4) if total > -1 else -1.0,
            "sharpe": round(sharpe, 2), "max_drawdown": round(mdd, 4),
            "dsr": deflated_sharpe_ratio(sr_p, r.size, n_trials=n_trials)}


def _spearman(a: np.ndarray, b: np.ndarray) -> float:
    """Corrélation de rang (Spearman) — robuste, pour l'Information Coefficient."""
    if a.size < 3:
        return 0.0
    ra = np.argsort(np.argsort(a)).astype(float)
    rb = np.argsort(np.argsort(b)).astype(float)
    ra -= ra.mean(); rb -= rb.mean()
    d = (ra.std() * rb.std())
    return float((ra * rb).mean() / d) if d else 0.0


def ml_walkforward(data: dict, step: int = 21, H: int = 21, lookback: int = 63,
                   top_n: int = 15, max_weight: float = 0.20, max_assets: int = 150,
                   max_train: int = 8000, cost_bps: float = 10.0, seed: int = 0) -> dict:
    """Backtest comparatif (ML walk-forward). Renvoie 3 courbes + métriques + IC + net de frais."""
    syms = [s for s, b in data.items() if b and len(b) > lookback + H + 2 * step][:max_assets]
    if len(syms) < 8:
        return {"available": False}
    L = min(len(data[s]) for s in syms)
    M = np.array([[b.close for b in data[s]][-L:] for s in syms], dtype=float)
    rets = M[:, 1:] / M[:, :-1] - 1
    rng = np.random.default_rng(seed)
    start = max(lookback, 60)
    ml_r, tech_r, bench_r = [], [], []
    ml_r_net, ic_tech, ic_ml = [], [], []
    prev_ml = np.zeros(len(syms))
    prev_tech = np.zeros(len(syms))
    turn = 0.0
    rebs = 0
    cost = cost_bps / 1e4
    for t in range(start, L - 1, step):
        # 1) jeu d'entraînement : labels réalisés (u + H <= t) → AUCUNE fuite
        us = list(range(lookback, t - H, 5))
        if len(us) < 6:
            continue
        X_tr, y_tr = [], []
        for u in us:
            f = _features(M, rets, u)
            lab = (M[:, u + H] > M[:, u]).astype(float)
            X_tr.append(f); y_tr.append(lab)
        X_tr = np.vstack(X_tr); y_tr = np.concatenate(y_tr)
        if X_tr.shape[0] > max_train:                     # borne le coût
            sel = rng.choice(X_tr.shape[0], max_train, replace=False)
            X_tr, y_tr = X_tr[sel], y_tr[sel]
        if len(set(y_tr.tolist())) < 2:
            continue
        model = LogitModel().fit(X_tr, y_tr)
        # 2) prédiction à t + 3) conviction technique
        ft = _features(M, rets, t)
        p_ml = np.asarray(model.predict_proba(ft), dtype=float)
        vol = ft[:, 4]
        conv_tech = (_z(ft[:, 1]) + _z(ft[:, 2]) - _z(vol)) / 3.0
        conv_ml = 0.5 * _z(conv_tech) + 0.5 * _z(p_ml)
        nxt = min(t + step, L - 1)
        fwd = M[:, nxt] / M[:, t] - 1

        def _alloc(conv):
            idx = np.argsort(conv)[::-1][:top_n]
            cv = np.clip(conv[idx], 0, None) / vol[idx]
            w = np.zeros(len(syms))
            if cv.sum() > 0:
                w[idx] = cv / cv.sum()
                w = np.minimum(w, max_weight); w /= (w.sum() or 1.0)
            return w

        w_ml, w_tech = _alloc(conv_ml), _alloc(conv_tech)
        to_ml = float(np.abs(w_ml - prev_ml).sum())
        ml_r.append(float((w_ml * fwd).sum()))
        ml_r_net.append(float((w_ml * fwd).sum()) - to_ml * cost)   # net de frais
        tech_r.append(float((w_tech * fwd).sum()))
        bench_r.append(float(fwd.mean()))
        ic_tech.append(_spearman(conv_tech, fwd))                   # pouvoir prédictif du signal
        ic_ml.append(_spearman(p_ml, fwd))
        turn += to_ml; prev_ml = w_ml; prev_tech = w_tech
        rebs += 1
    if rebs < 3:
        return {"available": False}
    py = 252.0 / step

    def _ic(xs):
        a = np.asarray(xs, dtype=float)
        m, s = float(a.mean()), float(a.std())
        return {"ic_mean": round(m, 4), "ic_tstat": round(m / s * np.sqrt(a.size), 2) if s else 0.0}

    return {"available": True, "n_rebalances": rebs, "step_days": step, "n_assets": len(syms),
            "ml": _metrics(ml_r, py, n_trials=30), "ml_net": _metrics(ml_r_net, py, n_trials=30),
            "tech": _metrics(tech_r, py, n_trials=15), "benchmark": _metrics(bench_r, py, n_trials=1),
            "turnover_annual": round(turn / rebs * py, 2),
            "ic_tech": _ic(ic_tech), "ic_ml": _ic(ic_ml), "cost_bps": cost_bps}
