"""Mesures relatives à un benchmark (esprit CFA / CIPM) — pures, testables.

beta, alpha de Jensen, tracking error, information ratio, R², up/down capture.
Entrées = rendements par période (mêmes longueurs). rf supposé 0 (ajustable).
"""

from __future__ import annotations

import numpy as np


def _align(p, b):
    p, b = np.asarray(p, float), np.asarray(b, float)
    n = min(len(p), len(b))
    return p[:n], b[:n]


def beta(port, bench) -> float:
    p, b = _align(port, bench)
    var = np.var(b, ddof=1)              # cohérent avec np.cov (ddof=1)
    return float(np.cov(p, b)[0, 1] / var) if var > 0 else 0.0


def jensen_alpha(port, bench, rf: float = 0.0) -> float:
    p, b = _align(port, bench)
    return float((p.mean() - rf) - beta(p, b) * (b.mean() - rf))


def tracking_error(port, bench) -> float:
    p, b = _align(port, bench)
    return float((p - b).std(ddof=1)) if len(p) > 1 else 0.0


def information_ratio(port, bench) -> float:
    p, b = _align(port, bench)
    te = tracking_error(p, b)
    return float((p - b).mean() / te) if te > 0 else 0.0


def r_squared(port, bench) -> float:
    p, b = _align(port, bench)
    if p.std() == 0 or b.std() == 0:
        return 0.0
    return float(np.corrcoef(p, b)[0, 1] ** 2)


def up_down_capture(port, bench) -> tuple[float, float]:
    p, b = _align(port, bench)
    up, dn = b > 0, b < 0
    uc = float(p[up].mean() / b[up].mean()) if up.any() and b[up].mean() != 0 else 0.0
    dc = float(p[dn].mean() / b[dn].mean()) if dn.any() and b[dn].mean() != 0 else 0.0
    return uc, dc


def relative_metrics(port_equity, bench_equity) -> dict:
    from packages.portfolio.metrics import returns_from_equity
    p, b = returns_from_equity(port_equity), returns_from_equity(bench_equity)
    uc, dc = up_down_capture(p, b)
    return {"beta": round(beta(p, b), 3), "alpha": round(jensen_alpha(p, b), 5),
            "tracking_error": round(tracking_error(p, b), 5),
            "information_ratio": round(information_ratio(p, b), 3),
            "r_squared": round(r_squared(p, b), 3),
            "up_capture": round(uc, 3), "down_capture": round(dc, 3)}
