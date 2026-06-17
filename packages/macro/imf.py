"""Projections FMI (World Economic Outlook) via l'API IMF DataMapper — GRATUIT, sans clé.

Indicateurs : croissance du PIB réel (NGDP_RPCH), inflation (PCPIPCH), chômage (LUR), par pays.
Les années ≥ année courante sont des **projections**. stdlib (urllib), dégrade proprement hors-ligne.
"""

from __future__ import annotations

import json
import urllib.request
from datetime import datetime, timezone

_BASE = "https://www.imf.org/external/datamapper/api/v1"
_COUNTRIES = [("USA", "🇺🇸 États-Unis"), ("FRA", "🇫🇷 France"), ("DEU", "🇩🇪 Allemagne"),
              ("CHE", "🇨🇭 Suisse"), ("GBR", "🇬🇧 Royaume-Uni"), ("JPN", "🇯🇵 Japon"),
              ("CHN", "🇨🇳 Chine"), ("IND", "🇮🇳 Inde"), ("KOR", "🇰🇷 Corée du Sud")]
_INDICATORS = [("NGDP_RPCH", "Croissance du PIB (%)"), ("PCPIPCH", "Inflation (%)"),
               ("LUR", "Chômage (%)")]


def _fetch(indicator: str) -> dict | None:
    try:
        codes = "/".join(c for c, _ in _COUNTRIES)
        with urllib.request.urlopen(f"{_BASE}/{indicator}/{codes}", timeout=8) as r:  # noqa: S310
            data = json.loads(r.read().decode())
        return data.get("values", {}).get(indicator, {})
    except Exception:  # noqa: BLE001
        return None


def imf_projections(n_years: int = 5) -> dict:
    """Tableaux croissance/inflation/chômage par pays (réalisé + projeté)."""
    cur = datetime.now(timezone.utc).year
    years = [str(y) for y in range(cur - 2, cur + n_years - 1)]
    out = {"available": False, "years": years, "current_year": cur,
           "countries": [{"flag": f} for _, f in _COUNTRIES], "indicators": []}
    any_ok = False
    for ind, label in _INDICATORS:
        vals = _fetch(ind)
        if not vals:
            continue
        any_ok = True
        rows = []
        for code, flag in _COUNTRIES:
            cv = vals.get(code, {})
            rows.append({"country": flag,
                         "values": [round(cv[y], 1) if y in cv and cv[y] is not None else None for y in years]})
        out["indicators"].append({"key": ind, "label": label, "rows": rows})
    out["available"] = any_ok
    if any_ok:
        out["source"] = "FMI — World Economic Outlook (DataMapper). Années ≥ courante = projections (e)."
    else:
        out["reason"] = "API IMF injoignable (réseau)."
    return out
