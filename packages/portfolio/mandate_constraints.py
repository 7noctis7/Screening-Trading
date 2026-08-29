"""Projection de poids long-only sous contraintes du mandat déclaratif."""

from __future__ import annotations

import numpy as np

from packages.mandate import Mandat, exiger_valide
from packages.portfolio.optimize import (
    equal_risk_contribution,
    hrp_weights,
    min_variance_weights,
)

_METHODS = {
    "erc": equal_risk_contribution,
    "min_var": min_variance_weights,
    "hrp": hrp_weights,
}


def _bounded_simplex(weights: np.ndarray, lower: float, upper: float) -> np.ndarray:
    n = weights.size
    if n * lower > 1.0 + 1e-12 or n * upper < 1.0 - 1e-12:
        raise ValueError("contraintes de poids infaisables pour le nombre d'actifs")
    w = np.clip(weights, lower, upper)
    for _ in range(100):
        residual = 1.0 - float(w.sum())
        if abs(residual) < 1e-10:
            return w
        free = (w < upper - 1e-12) if residual > 0 else (w > lower + 1e-12)
        if not free.any():
            break
        w[free] += residual / int(free.sum())
        w = np.clip(w, lower, upper)
    raise ValueError("projection du mandat non convergente")


def mandated_allocation(
    cov, symbols: list[str], mandat: Mandat, method: str = "erc"
) -> dict[str, float]:
    """Calcule ERC/Min-Var/HRP puis applique les hard constraints du mandat."""
    exiger_valide(mandat)
    if method not in _METHODS:
        raise ValueError(f"méthode inconnue : {method}")
    c = mandat.contraintes
    if len(symbols) < int(c.get("nb_lignes_min", 0)):
        raise ValueError("univers plus petit que contraintes.nb_lignes_min")
    if len(symbols) > int(c.get("nb_lignes_max", len(symbols))):
        raise ValueError("univers plus grand que contraintes.nb_lignes_max")
    allowed = set(c.get("univers_autorise", symbols)) - set(
        c.get("univers_interdit", ())
    )
    if set(symbols) - allowed:
        raise ValueError("l'univers contient un symbole interdit par le mandat")
    raw = np.asarray(_METHODS[method](cov), float)
    if raw.size != len(symbols):
        raise ValueError("covariance et symboles incompatibles")
    lower = float(c.get("poids_min_ligne", 0.0))
    upper = float(c.get("poids_max_ligne", 1.0))
    projected = _bounded_simplex(raw, lower, upper)
    return {symbol: float(projected[i]) for i, symbol in enumerate(symbols)}
