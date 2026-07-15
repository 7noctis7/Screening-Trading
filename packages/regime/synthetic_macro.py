"""Provider macro synthétique (offline) — génère des observations VINTAGE déterministes
avec délai de publication (realtime_start = obs_date + lag) pour démos/tests."""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

from packages.core.models import MacroObservation


def synthetic_macro(start: datetime, months: int = 36, lag_days: int = 30
                    ) -> list[MacroObservation]:
    obs: list[MacroObservation] = []
    for i in range(months):
        d = _add_month(start, i)
        rt = d + timedelta(days=lag_days)  # publié avec délai
        phase = i / 6.0
        obs += [
            MacroObservation("T10Y3M", d, 0.5 * math.sin(phase) - 0.3, rt),  # courbe (id aligné ingest)
            MacroObservation("ISM", d, 52 + 6 * math.sin(phase), rt),         # PMI
            MacroObservation("UNRATE", d, 4.0 + 0.5 * (1 - math.cos(phase)), rt),
            MacroObservation("VIXCLS", d, 16 + 8 * abs(math.sin(phase * 1.3)), rt),
            MacroObservation("FEDFUNDS", d, 4.5 + math.sin(phase), rt),
        ]
    return obs


def _add_month(d: datetime, n: int) -> datetime:
    m = d.month - 1 + n
    return datetime(d.year + m // 12, m % 12 + 1, 1, tzinfo=timezone.utc)
