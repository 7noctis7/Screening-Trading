"""Client FRED (Réserve fédérale de St. Louis) — données macro CHIFFRÉES, gratuit.

FRED agrège US + international (OCDE/Eurostat/BCE). Clé gratuite : https://fred.stlouisfed.org →
My Account → API Keys, puis `export FRED_API_KEY=...`. Chaque série est récupérée indépendamment
(dégrade proprement si absente/hors-ligne). `units` : lin (niveau), pc1 (variation a/a %),
chg (variation période). stdlib (urllib).
"""

from __future__ import annotations

import json
import os
import urllib.request

_BASE = "https://api.stlouisfed.org/fred/series/observations"

# (series_id, libellé, groupe, unité, suffixe d'affichage)
SERIES: list[tuple] = [
    ("UNRATE", "Chômage", "🇺🇸 États-Unis", "lin", "%"),
    ("CPIAUCSL", "Inflation (IPC, a/a)", "🇺🇸 États-Unis", "pc1", "%"),
    ("FEDFUNDS", "Taux directeur Fed", "🇺🇸 États-Unis", "lin", "%"),
    ("DGS2", "Taux 2 ans", "🇺🇸 États-Unis", "lin", "%"),
    ("DGS10", "Taux 10 ans", "🇺🇸 États-Unis", "lin", "%"),
    ("INDPRO", "Production indus. (a/a)", "🇺🇸 États-Unis", "pc1", "%"),
    ("UMCSENT", "Confiance ménages", "🇺🇸 États-Unis", "lin", ""),
    ("LRHUTTTTEZM156S", "Chômage", "🇪🇺 Zone euro", "lin", "%"),
    ("CP0000EZ19M086NEST", "Inflation (IPCH, a/a)", "🇪🇺 Zone euro", "pc1", "%"),
    ("IRLTLT01DEM156N", "Taux 10 ans (Bund)", "🇩🇪 Allemagne", "lin", "%"),
    ("DCOILWTICO", "Pétrole WTI", "🛢️ Marchés", "lin", "$"),
    ("VIXCLS", "VIX (volatilité)", "🛢️ Marchés", "lin", ""),
    ("T10Y2Y", "Courbe 10a − 2a", "🛢️ Marchés", "lin", " pts"),
    ("BAMLH0A0HYM2", "Spread haut rendement", "🛢️ Marchés", "lin", "%"),
]


def _fetch(series_id: str, units: str, key: str) -> dict | None:
    try:
        url = (f"{_BASE}?series_id={series_id}&api_key={key}&file_type=json"
               f"&units={units}&sort_order=desc&limit=2")
        with urllib.request.urlopen(url, timeout=6) as r:  # noqa: S310
            obs = json.loads(r.read().decode()).get("observations", [])
        vals = [(o["date"], float(o["value"])) for o in obs if o.get("value") not in (".", None, "")]
        if not vals:
            return None
        (d0, v0) = vals[0]
        delta = round(v0 - vals[1][1], 2) if len(vals) > 1 else None
        return {"value": round(v0, 2), "date": d0, "delta": delta}
    except Exception:  # noqa: BLE001
        return None


def macro_snapshot() -> dict:
    """Tableau macro chiffré (FRED). {available, groups:{groupe:[{label,value,unit,date,delta}]}}."""
    key = os.environ.get("FRED_API_KEY")
    if not key:
        return {"available": False, "reason": "FRED_API_KEY absente (clé gratuite sur fred.stlouisfed.org)"}
    groups: dict[str, list] = {}
    for sid, label, group, units, unit in SERIES:
        d = _fetch(sid, units, key)
        if d:
            groups.setdefault(group, []).append({"label": label, "unit": unit, **d})
    if not groups:
        return {"available": False, "reason": "FRED injoignable (réseau ou clé invalide)"}
    return {"available": True, "groups": groups,
            "source": "FRED (Réserve fédérale de St. Louis) — agrège OCDE/Eurostat/BCE. Dernière valeur publiée."}
