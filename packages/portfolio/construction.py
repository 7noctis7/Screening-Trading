"""Construction de portefeuille — risk-parity + bande de non-trading + exposition pilotée
par un DRAWDOWN-CIBLE (best practice : on choisit le risque, le rendement en découle).

Étapes :
  1. poids **risk-parity (ERC)** sur les actifs détenus (chaque actif contribue également au risque) ;
  2. **exposition brute** dimensionnée pour viser une volatilité ⇒ un drawdown cible
     (heuristique robuste : maxDD ≈ k × vol annualisée, k≈2.5) ;
  3. **bande de non-trading** vs l'allocation actuelle (réduit le turnover).
Numpy pur, testable. Sert d'allocation RECOMMANDÉE (le swing reste le sélectionneur).
"""

from __future__ import annotations

import numpy as np

from packages.portfolio.optimize import equal_risk_contribution


def vol_target_from_drawdown(dd_target: float, k: float = 2.5) -> float:
    """Volatilité annualisée cible déduite d'un drawdown cible (maxDD ≈ k·vol)."""
    return max(0.0, abs(dd_target)) / k


def tail_adjusted_dd_target(dd_target: float, tail_ratio: float | None,
                            gaussian_ref: float = 1.29) -> float:
    """Ticket #5 (Simons) : durcit le DD-cible quand les queues sont ÉPAISSES (tail_ratio = CVaR/VaR
    > référence gaussienne ≈ 1.29) → on dimensionne sur le risque de queue, pas la vol gaussienne.
    Renvoie le DD-cible effectif (≤ dd_target)."""
    if not tail_ratio or tail_ratio <= gaussian_ref:
        return dd_target
    return dd_target * (gaussian_ref / tail_ratio)


def build_target(symbols: list[str], cov, current_weights: dict[str, float] | None = None,
                 dd_target: float = 0.25, band: float = 0.03, max_gross: float = 1.0) -> dict:
    """Allocation cible risk-parity, exposition pilotée par le drawdown-cible, bande de non-trading.

    Args:
        symbols / cov : actifs et covariance (annualisée) — même ordre.
        current_weights : allocation actuelle (pour la bande).
        dd_target : drawdown max accepté (ex. 0.25 = −25 %).
        band : seuil de non-trading (ex. 0.03 = 3 %).
        max_gross : exposition brute maximale (1.0 = pas de levier).
    """
    C = np.asarray(cov, dtype=float)
    n = len(symbols)
    if n == 0 or C.shape[0] != n:
        return {"available": False}
    w_rp = np.array(equal_risk_contribution(C))
    port_vol = float(np.sqrt(max(0.0, w_rp @ C @ w_rp)))         # vol à plein investissement
    tgt_vol = vol_target_from_drawdown(dd_target)
    gross = 0.0 if port_vol <= 0 else min(max_gross, tgt_vol / port_vol)
    target = w_rp * gross
    cur = np.array([(current_weights or {}).get(s, 0.0) for s in symbols])
    # bande de non-trading : on ne bouge un poids que s'il dérive de plus de `band`
    if band > 0 and cur.sum() > 0:
        target = np.where(np.abs(target - cur) < band, cur, target)
    rows = [{"symbol": s, "current": round(float(cur[i]), 4), "target": round(float(target[i]), 4),
             "risk_parity": round(float(w_rp[i]), 4)} for i, s in enumerate(symbols)]
    rows.sort(key=lambda r: r["target"], reverse=True)
    drift = float(np.abs(target - cur).sum())
    return {"available": True, "rows": rows,
            "gross_exposure": round(float(target.sum()), 4),
            "cash_pct": round(float(max(0.0, 1.0 - target.sum())), 4),
            "portfolio_vol_full": round(port_vol, 4), "target_vol": round(tgt_vol, 4),
            "dd_target": dd_target, "band": band, "rebalance_drift": round(drift, 4),
            "note": "Risk-parity × exposition pour viser le DD cible ; bande de non-trading pour limiter le turnover."}
