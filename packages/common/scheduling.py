"""Cadence des jobs planifiés (orchestration). Helpers purs, testables.

L'univers se reconstruit MENSUELLEMENT : `due_for_rebuild` décide s'il faut
relancer en fonction du dernier snapshot. Le runner APScheduler (scripts/scheduler.py)
appelle ça ; un cron mensuel marche aussi (cf. vault 14 / README).
"""

from __future__ import annotations

from datetime import date, datetime, timezone


def due_for_rebuild(last_snapshot: str | None, cadence_days: int = 30,
                    now: datetime | None = None) -> bool:
    """True s'il n'y a pas de snapshot ou si le dernier date de plus de `cadence_days`."""
    if not last_snapshot:
        return True
    now = now or datetime.now(timezone.utc)
    try:
        last = date.fromisoformat(last_snapshot)
    except ValueError:
        return True
    return (now.date() - last).days >= cadence_days
