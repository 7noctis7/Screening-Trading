"""Optimisation de portefeuille — IVP, min-variance, HRP simplifié (sans scipy).

Best practices (PyPortfolioOpt / Riskfolio) : proposer une **allocation alternative** plus robuste
que l'équipondération. HRP (López de Prado) évite l'inversion instable de la matrice de covariance
en allouant par bisection récursive sur un ordre issu de la corrélation. Numpy pur, long-only.
"""

from __future__ import annotations

import numpy as np


def inverse_variance_weights(cov) -> list[float]:
    """IVP : poids ∝ 1/variance (diagonale). Robuste, sans inversion de matrice."""
    C = np.asarray(cov, dtype=float)
    if C.size == 0:
        return []
    iv = 1.0 / np.clip(np.diag(C), 1e-12, None)
    return (iv / iv.sum()).tolist()


def min_variance_weights(cov) -> list[float]:
    """Portefeuille à variance minimale (long-only via clipping + renormalisation)."""
    C = np.asarray(cov, dtype=float)
    n = C.shape[0]
    if n == 0:
        return []
    try:
        inv = np.linalg.pinv(C)
        w = inv @ np.ones(n)
        w = np.clip(w, 0.0, None)
        s = w.sum()
        return (w / s).tolist() if s > 0 else [1.0 / n] * n
    except Exception:  # noqa: BLE001
        return [1.0 / n] * n


def equal_risk_contribution(cov, iters: int = 500) -> list[float]:
    """Risk parity (ERC) : chaque actif contribue également au risque (algo itératif, long-only)."""
    C = np.asarray(cov, dtype=float)
    n = C.shape[0]
    if n == 0:
        return []
    if n == 1:
        return [1.0]
    w = np.ones(n) / n
    for _ in range(iters):
        rc = w * (C @ w)                       # contributions au risque
        target = rc.mean()
        grad = rc - target
        w = np.clip(w - 0.01 * grad, 1e-6, None)
        w /= w.sum()
    return w.tolist()


def _seriation(corr: np.ndarray) -> list[int]:
    """Ordre quasi-diagonal : seriation gloutonne par plus forte corrélation (proxy linkage)."""
    n = corr.shape[0]
    remaining = list(range(n))
    order = [remaining.pop(0)]
    while remaining:
        last = order[-1]
        nxt = max(remaining, key=lambda j: corr[last, j])
        order.append(nxt)
        remaining.remove(nxt)
    return order


def hrp_weights(cov) -> list[float]:
    """HRP simplifié : seriation par corrélation puis bisection récursive inverse-variance."""
    C = np.asarray(cov, dtype=float)
    n = C.shape[0]
    if n == 0:
        return []
    if n == 1:
        return [1.0]
    d = np.sqrt(np.clip(np.diag(C), 1e-12, None))
    corr = C / np.outer(d, d)
    corr = np.clip(np.nan_to_num(corr, nan=0.0), -1.0, 1.0)
    order = _seriation(corr)
    w = np.ones(n)
    var = np.clip(np.diag(C), 1e-12, None)

    def _cluster_var(idx):
        sub = var[idx]
        iv = (1.0 / sub) / (1.0 / sub).sum()
        return float(iv @ C[np.ix_(idx, idx)] @ iv)

    def _bisect(items):
        if len(items) <= 1:
            return
        half = len(items) // 2
        left, right = items[:half], items[half:]
        vl, vr = _cluster_var(left), _cluster_var(right)
        a = 1.0 - vl / (vl + vr) if (vl + vr) > 0 else 0.5
        for i in left:
            w[i] *= a
        for i in right:
            w[i] *= (1.0 - a)
        _bisect(left)
        _bisect(right)

    _bisect(order)
    s = w.sum()
    return (w / s).tolist() if s > 0 else [1.0 / n] * n
