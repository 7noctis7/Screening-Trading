"""Provider FRED/ALFRED (réel, réseau) → MacroObservation VINTAGE.

FRED renvoie les observations ; en demandant les vintages (realtime), ALFRED fournit
le `realtime_start` (date de publication) → point-in-time. Le parser `parse_observations`
est pur et testable avec une fixture JSON. Clé via env FRED_API_KEY (gratuit, illimité).
"""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from packages.core.models import MacroObservation

_BASE = "https://api.stlouisfed.org/fred/series/observations"


def parse_observations(payload: dict, series_id: str) -> list[MacroObservation]:
    """JSON FRED/ALFRED → observations vintage. Ignore les valeurs manquantes ('.')."""
    out: list[MacroObservation] = []
    for o in payload.get("observations", []):
        v = o.get("value", ".")
        if v in (".", "", None):
            continue
        try:
            value = float(v)
        except ValueError:
            continue
        out.append(MacroObservation(
            series_id=series_id,
            obs_date=_d(o["date"]),
            value=value,
            realtime_start=_d(o.get("realtime_start", o["date"]))))
    return out


class FredProvider:
    name = "fred"

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or os.environ.get("FRED_API_KEY", "")

    def fetch(self, series_id: str, vintages: bool = True) -> list[MacroObservation]:
        params = {"series_id": series_id, "api_key": self.api_key, "file_type": "json"}
        if vintages:  # ALFRED : toutes les révisions telles que publiées
            params["realtime_start"] = "1776-07-04"
            params["realtime_end"] = "9999-12-31"
        url = f"{_BASE}?{urllib.parse.urlencode(params)}"
        with urllib.request.urlopen(url, timeout=30) as r:
            payload = json.loads(r.read().decode())
        return parse_observations(payload, series_id)


def _d(s: str) -> datetime:
    return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)
