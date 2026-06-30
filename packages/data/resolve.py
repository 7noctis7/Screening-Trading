"""Résolution de valeur à 3 étages avec PROVENANCE — anti-cascade de N/D.

Éthique : on n'INVENTE jamais. Mais on peut (1) réutiliser la vraie donnée d'hier
(carry-forward, étiqueté + incertitude gonflée √k), (2) imputer par les pairs du
cross-section (médiane sectorielle / modèle factoriel, étiqueté), sinon (3) DROP l'actif
(pas de fantôme dans le z-score). La provenance circule jusqu'au front (transparence).
"""

from __future__ import annotations

import statistics


def resolve(fresh: float | None, stale: float | None = None, stale_days: int = 0,
            peers: list[float] | None = None) -> tuple[float | None, str]:
    """→ (valeur, provenance ∈ {fresh, stale:Nd, imputed_xs, dropped})."""
    if fresh is not None:
        return fresh, "fresh"
    if stale is not None:
        return stale, f"stale:{stale_days}d"
    vals = [p for p in (peers or []) if p is not None]
    if len(vals) >= 3:                       # médiane des pairs (≥3 pour être robuste)
        return statistics.median(vals), "imputed_xs"
    return None, "dropped"                    # exclu du cross-section


def uncertainty_mult(provenance: str) -> float:
    """Facteur de gonflement d'incertitude selon la fraîcheur (vol ~ √temps)."""
    if provenance == "fresh":
        return 1.0
    if provenance.startswith("stale:"):
        try:
            k = int(provenance.split(":")[1].rstrip("d"))
        except (ValueError, IndexError):
            k = 1
        return (1 + k) ** 0.5
    if provenance == "imputed_xs":
        return 1.5                            # imputation = confiance dégradée
    return float("inf")


def within_drop_budget(provenances: list[str], max_imputed_ratio: float = 0.3) -> bool:
    """L'actif reste-t-il fiable ? Trop d'inputs stale/imputés → on le retire (DROP)."""
    if not provenances:
        return False
    bad = sum(1 for p in provenances if p != "fresh" and not p.startswith("stale:1"))
    return bad / len(provenances) <= max_imputed_ratio
