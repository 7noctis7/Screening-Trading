"""Black-Litterman : combine l'équilibre de marché (prior) avec des VUES (conviction) → rendements
postérieurs robustes, puis poids moyenne-variance. Référence buy-side pour intégrer des signaux
faibles sans exploser le risque. numpy pur.

- Prior (reverse optimization) : Π = δ · Σ · w_marché.
- Vues : P (matrice de sélection) · Q (rendements attendus) · Ω (incertitude des vues).
- Postérieur : μ = [(τΣ)⁻¹ + Pᵀ Ω⁻¹ P]⁻¹ [(τΣ)⁻¹ Π + Pᵀ Ω⁻¹ Q].
"""

from __future__ import annotations

import numpy as np


def market_implied_returns(cov, w_mkt, risk_aversion: float = 2.5) -> np.ndarray:
    """Rendements d'équilibre implicites (reverse optimization) : Π = δ Σ w."""
    return risk_aversion * np.asarray(cov, float) @ np.asarray(w_mkt, float)


def black_litterman(cov, w_mkt, P, Q, omega=None, tau: float = 0.05,
                    risk_aversion: float = 2.5) -> dict:
    """Rendements postérieurs + poids long-only normalisés. P/Q peuvent être vides (→ prior)."""
    Sigma = np.asarray(cov, float)
    n = Sigma.shape[0]
    w_mkt = np.asarray(w_mkt, float)
    pi = market_implied_returns(Sigma, w_mkt, risk_aversion)
    P = np.asarray(P, float).reshape(-1, n) if np.size(P) else np.zeros((0, n))
    Q = np.asarray(Q, float).reshape(-1) if np.size(Q) else np.zeros(0)
    tauS = tau * Sigma
    tauS_inv = np.linalg.pinv(tauS)
    if P.shape[0] == 0:                                   # aucune vue → postérieur = prior
        mu = pi
    else:
        if omega is None:
            omega = np.diag(np.clip(np.diag(P @ tauS @ P.T), 1e-10, None))
        om_inv = np.linalg.pinv(np.asarray(omega, float))
        A = tauS_inv + P.T @ om_inv @ P
        b = tauS_inv @ pi + P.T @ om_inv @ Q
        mu = np.linalg.solve(A, b)
    w = np.linalg.pinv(risk_aversion * Sigma) @ mu       # poids moyenne-variance
    w = np.clip(w, 0.0, None)
    s = w.sum()
    w = w / s if s > 0 else np.full(n, 1.0 / n)
    return {"prior_returns": [round(float(x), 5) for x in pi],
            "posterior_returns": [round(float(x), 5) for x in mu],
            "weights": [round(float(x), 4) for x in w]}


def views_from_scores(scores: list[float], scale: float = 0.04) -> tuple[np.ndarray, np.ndarray]:
    """Construit des vues ABSOLUES à partir de scores z (conviction) : P = I, Q = z·scale (borné).

    Renvoie (P, Q). Les actifs sans score (NaN) sont exclus des vues.
    """
    z = np.asarray(scores, float)
    n = len(z)
    rows, q = [], []
    mu, sd = np.nanmean(z), (np.nanstd(z) or 1.0)
    for i in range(n):
        if np.isnan(z[i]):
            continue
        e = np.zeros(n); e[i] = 1.0
        rows.append(e)
        q.append(float(np.clip((z[i] - mu) / sd, -2.5, 2.5) * scale))
    if not rows:
        return np.zeros((0, n)), np.zeros(0)
    return np.asarray(rows), np.asarray(q)
