"""Budget de risque — contribution de chaque position à la volatilité du portefeuille.

Best practice institutionnelle (risk parity / risk budgeting) : ce n'est pas le poids en
capital qui compte, mais la **contribution au risque**. On décompose la variance du portefeuille
en contributions par position (MCTR = contribution marginale, PCTR = contribution composante,
dont la somme vaut la variance totale). Numpy pur, testable hors-ligne.
"""

from __future__ import annotations

import numpy as np


def risk_contributions(weights, cov) -> dict:
    """Décompose le risque du portefeuille en contributions par position.

    Args:
        weights: poids des positions (somme idéalement = 1).
        cov: matrice de covariance des rendements (n×n), même ordre que weights.
    Returns:
        {portfolio_vol, contrib_pct:[...], mctr:[...], diversification_ratio}.
    """
    w = np.asarray(weights, dtype=float)
    C = np.asarray(cov, dtype=float)
    if w.size == 0 or C.size == 0 or C.shape[0] != w.size:
        return {"portfolio_vol": 0.0, "contrib_pct": [], "mctr": [], "diversification_ratio": 0.0}
    port_var = float(w @ C @ w)
    if port_var <= 0:
        eq = [1.0 / w.size] * w.size
        return {"portfolio_vol": 0.0, "contrib_pct": eq, "mctr": [0.0] * w.size,
                "diversification_ratio": 1.0}
    port_vol = port_var ** 0.5
    mctr = (C @ w) / port_vol                      # contribution marginale à la vol
    pctr = w * mctr                                # contribution composante (somme = port_vol)
    total = float(pctr.sum()) or 1.0
    contrib_pct = (pctr / total).tolist()
    # ratio de diversification : Σ(wᵢσᵢ) / σ_portefeuille (>1 = diversifié)
    stdev = np.sqrt(np.clip(np.diag(C), 0, None))
    dr = float((w @ stdev) / port_vol) if port_vol else 1.0
    return {"portfolio_vol": round(port_vol, 6),
            "contrib_pct": [round(x, 4) for x in contrib_pct],
            "mctr": [round(float(x), 6) for x in mctr],
            "diversification_ratio": round(dr, 3)}


def covariance(returns_by_asset: dict[str, list[float]]) -> tuple[list[str], np.ndarray]:
    """Matrice de covariance (annualisée ×252) à partir des rendements par actif (alignés).

    Délègue au moteur vectorisé unique (`packages.data.engine.covariance_matrix`) — source de
    vérité partagée avec le screener, prête pour l'accélération DuckDB/Polars. Repli numpy local
    si le moteur est indisponible : ne casse jamais le snapshot."""
    syms = list(returns_by_asset)
    if not syms:
        return [], np.zeros((0, 0))
    try:
        from packages.data.engine import covariance_matrix
        cb_syms, cov = covariance_matrix(returns_by_asset, annualize=252)
        # le moteur filtre les séries trop courtes (<2 pts) ; on aligne la sortie sur l'attendu
        if len(cb_syms) == len(syms):
            return cb_syms, np.atleast_2d(np.asarray(cov, dtype=float))
        if cb_syms:
            return cb_syms, np.atleast_2d(np.asarray(cov, dtype=float))
    except Exception:  # noqa: BLE001 — moteur indisponible → repli numpy pur ci-dessous
        pass
    n = min(len(v) for v in returns_by_asset.values())
    M = np.array([returns_by_asset[s][-n:] for s in syms], dtype=float)
    cov = np.cov(M) * 252.0 if n > 1 else np.zeros((len(syms), len(syms)))
    return syms, np.atleast_2d(cov)
