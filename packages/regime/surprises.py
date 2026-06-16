"""Surprises économiques — ce qui bouge les marchés = réalisé vs consensus.

Agrège les surprises normalisées récentes (esprit Citi Economic Surprise Index)
en signaux exploitables : surprise globale + par thème (inflation, croissance, emploi).
Point-in-time : ne considérer que les releases dont release_date <= t.
"""

from __future__ import annotations

from datetime import datetime

from packages.core.models import EconomicRelease

# Mapping série → thème (pour des surprises thématiques)
_THEME = {
    "CPIAUCSL": "inflation", "PCEPILFE": "inflation", "CPI": "inflation",
    "PAYEMS": "growth", "ISM": "growth", "GDP": "growth", "PMI": "growth",
    "UNRATE": "employment", "ICSA": "employment", "NFP": "employment",
}


def surprise_index(releases: list[EconomicRelease], as_of: datetime,
                   window_days: int = 90) -> dict[str, float]:
    """Surprise moyenne (z) globale + par thème sur la fenêtre récente, point-in-time."""
    recent = [r for r in releases
              if r.release_date <= as_of
              and (as_of - r.release_date).days <= window_days]
    out: dict[str, float] = {"overall": 0.0}
    if not recent:
        return out
    out["overall"] = sum(r.surprise_z for r in recent) / len(recent)
    by_theme: dict[str, list[float]] = {}
    for r in recent:
        by_theme.setdefault(_THEME.get(r.series_id, "other"), []).append(r.surprise_z)
    for theme, vals in by_theme.items():
        out[theme] = sum(vals) / len(vals)
    return out
