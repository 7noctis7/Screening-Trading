"""Garde point-in-time (anti-look-ahead) — la fuite de données est l'ennemie n°1.

Règle : une observation n'est utilisable à la date `t` que si elle était CONNUE à t,
c.-à-d. `realtime_start ≤ t` (date de publication/dépôt, pas la date de période).
- pit_filter : ne garde que le connu à t.
- assert_no_leak : lève si une obs « du futur » entre dans un calcul passé (test CI).
- stable_prefix : vérifie qu'un recalcul du passé ne change PAS le passé (sentinelle
  de reproductibilité point-in-time — le test en or contre la fuite par révision).
"""

from __future__ import annotations

from datetime import datetime


def pit_filter(records: list[dict], as_of: datetime,
               rt_key: str = "realtime_start") -> list[dict]:
    """Sous-ensemble connu à `as_of` (realtime_start ≤ as_of)."""
    return [r for r in records if r.get(rt_key) is not None and r[rt_key] <= as_of]


def assert_no_leak(records: list[dict], as_of: datetime,
                   rt_key: str = "realtime_start") -> None:
    """Lève AssertionError si une obs publiée APRÈS `as_of` est présente (fuite)."""
    leaks = [r for r in records if r.get(rt_key) is not None and r[rt_key] > as_of]
    if leaks:
        raise AssertionError(
            f"Look-ahead : {len(leaks)} obs publiées après {as_of.isoformat()} "
            f"(ex. {leaks[0].get(rt_key)})")


def stable_prefix(series_full: list[float], series_past: list[float],
                  tol: float = 1e-9) -> bool:
    """Sentinelle : reconstruire le passé doit donner EXACTEMENT le passé.

    `series_past` = features rebâties figées à T−k ; `series_full` = jusqu'à T tronqué
    à la même longueur. Toute différence = fuite (révision future → passé modifié).
    """
    n = min(len(series_full), len(series_past))
    return all(abs(series_full[i] - series_past[i]) <= tol for i in range(n))
