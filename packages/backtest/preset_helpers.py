"""Helpers pour preset_backtest — optimisation, régime, risque. Extracteur de 867→400."""

from __future__ import annotations

import numpy as np


def regime_mult(mkt: np.ndarray, t: int, *, dd_hard: float = -0.15,
                dd_soft: float = -0.10, g_dist: float = 0.6,
                g_below: float = 0.2) -> float:
    """#5 porte de régime + #6 frein de drawdown sur l'indice marché."""
    if t < 25:
        return 1.0
    hist = mkt[:t + 1]
    ma = hist[-200:].mean()
    slope = mkt[t] / mkt[t - 20] - 1.0
    peak = float(np.maximum.accumulate(hist)[-1])
    dd = mkt[t] / peak - 1.0 if peak > 0 else 0.0
    if dd < dd_hard:
        return 0.0
    g = 1.0 if (mkt[t] > ma and slope > 0) else (g_dist if mkt[t] > ma else g_below)
    if dd < dd_soft:
        g *= 0.5
    return g


def mom_tilt(A: np.ndarray, t: int, w: np.ndarray, gamma: float = 1.0) -> np.ndarray:
    """#4 incline vers leaders (momentum 12m)."""
    base = A[:, max(0, t - 252)]
    mom = np.where(base > 0, A[:, t] / base - 1.0, 0.0)
    tilt = np.clip(mom, 0.0, None) ** gamma
    if float(tilt.sum()) <= 0:
        return w
    f = 0.5 + 0.5 * tilt / (tilt.mean() + 1e-9)
    w2 = w * f
    s = float(w2.sum())
    return w2 / s if s > 0 else w


def breadth(A: np.ndarray, t: int) -> float:
    """#8 ampleur de marché : fraction univers au-dessus MM200."""
    if t < 25:
        return 1.0
    lo = max(0, t - 200)
    above = [A[i, t] > A[i, lo:t].mean() for i in range(A.shape[0]) if t - lo > 5]
    return float(np.mean(above)) if above else 1.0


def cap_weights(w: np.ndarray, max_weight: float) -> np.ndarray:
    """Plafond de concentration itéré."""
    for _ in range(3):
        over = w > max_weight
        if not over.any():
            break
        excess = (w[over] - max_weight).sum()
        w[over] = max_weight
        free = ~over & (w > 0)
        if free.any():
            w[free] += excess * w[free] / w[free].sum()
        else:
            break
    s = w.sum()
    return w / s if s > 0 else w


def adaptive_cap(cov: np.ndarray, max_weight: float, corr_tighten: bool,
                 stress_corr: float = 0.60, tighten: float = 0.5,
                 floor: float = 0.05) -> float:
    """Plafond resserré si corrélation monte."""
    if not corr_tighten or cov.shape[0] < 3:
        return max_weight
    d = np.sqrt(np.clip(np.diag(cov), 1e-12, None))
    corr = cov / np.outer(d, d)
    n = corr.shape[0]
    avg = float((corr.sum() - n) / (n * (n - 1)))
    return max(floor, round(max_weight * tighten, 4)) if avg > stress_corr else max_weight


def select_rolling_universe(M: dict, t: int, top_k: int, lookback: int) -> list:
    """Top-K actifs par momentum à l'instant t (point-in-time, pas de fuite)."""
    if len(M) < 5:
        return list(M.keys())[:top_k]
    _s0 = max(lookback, 50)
    if t < _s0:
        return list(M.keys())[:top_k]
    _b0 = max(0, t - 252 - 1)
    sel = {s: float(M[s][t - 1] / M[s][_b0] - 1)
           for s in M
           if len(M[s]) > t and np.isfinite(M[s][t - 1])
           and np.isfinite(M[s][_b0]) and M[s][_b0] > 0}
    return (sorted(sel, key=lambda s: sel[s], reverse=True)[:top_k]
            if len(sel) >= 5 else list(M.keys())[:top_k])


def regime_detail(mkt: np.ndarray, t: int) -> str:
    """Les CHIFFRES derrière `regime_mult` — drawdown, pic, MM200, pente.

    Trois hypothèses fausses ont été émises sur un `régime = 0.000` faute de savoir
    QUELLE branche l'annulait. Le multiplicateur seul ne le dit pas : 0,0 ne peut venir
    que du drawdown dur, mais 0,2 et 0,6 se ressemblent, et rien n'indique si le niveau
    est légitime. Cette fonction n'entre dans AUCUN calcul ; elle décrit.
    """
    if t < 25:
        return "moins de 25 barres → porte neutralisée (1,0)"
    hist = mkt[:t + 1]
    peak_i = int(np.argmax(np.maximum.accumulate(hist)[-1] == hist))
    peak = float(hist[peak_i])
    dd = mkt[t] / peak - 1.0 if peak > 0 else 0.0
    ma = float(hist[-200:].mean())
    slope = float(mkt[t] / mkt[t - 20] - 1.0)
    recul = t - peak_i
    return (f"DD {dd:+.1%} (pic il y a {recul} barres) · "
            f"niveau {mkt[t]:.2f} vs MM200 {ma:.2f} · pente 20j {slope:+.1%}")
