"""Peuple un MacroStore avec des séries macro RÉELLES pour le classifieur de régime —
remplace le repli synthétique (`synthetic_macro`).

Sources (toutes gratuites) :
- **VIXCLS**  ← VIX réel (^VIX) déjà chargé dans le snapshot ;
- **ISM**     ← proxy d'activité dérivé de la **tendance S&P 500** (momentum 6 mois mappé
               autour de 50 : marché qui monte = expansion, qui baisse = contraction) ;
- **T10Y2Y** et **UNRATE** ← **FRED** point-in-time (vintages ALFRED) si `FRED_API_KEY`.

Le classifieur (`MacroRegimeClassifier`) lit ces IDs. Tout est dégradable : sans clé FRED on
garde VIX + tendance S&P (déjà bien meilleur que le synthétique) ; sans rien → l'appelant
retombe sur `synthetic_macro`.
"""

from __future__ import annotations

from datetime import datetime, timezone

import numpy as np

from packages.core.models import MacroObservation
from packages.storage import MacroStore


def _dt(d) -> datetime:
    if isinstance(d, datetime):
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    return datetime.fromisoformat(str(d)[:19]).replace(tzinfo=timezone.utc)


def real_macro_store(vix_vals, vix_dates, sp_closes, sp_dates,
                     fred_key: str | None = None) -> tuple[MacroStore, dict, bool]:
    """Renvoie (store, sources, is_real). `sources` = {série: provenance} pour l'affichage."""
    # P1-3 (2026-07-06) : PERSISTANT par défaut → les vintages ALFRED ingérés par
    # `make ingest-macro` (Mac, FRED_API_KEY) survivent entre les builds et priment
    # sur les proxys. QUANT_MACRO_DB=':memory:' pour un store jetable (tests/offline).
    import os
    from pathlib import Path as _P
    _db = os.environ.get("QUANT_MACRO_DB", "data/macro.db")
    if _db != ":memory:":
        _P(_db).parent.mkdir(parents=True, exist_ok=True)
    store = MacroStore(_db)
    sources: dict[str, str] = {}

    # Alignement défensif valeurs↔dates : le calendrier univers peut être plus court que la série
    # d'indice réelle (ex. en CI, ^GSPC a plus de barres que la plus longue action) → on tronque sur
    # le commun par la fin pour éviter tout IndexError (sinon le snapshot entier plante).
    def _align(vals, dates):
        k = min(len(vals), len(dates))
        return (list(vals)[-k:], list(dates)[-k:]) if k else ([], [])
    vix_vals, vix_dates = _align(vix_vals, vix_dates)
    sp_closes, sp_dates = _align(sp_closes, sp_dates)

    # VIX réel
    vobs = [MacroObservation("VIXCLS", _dt(d), float(v), _dt(d))
            for d, v in zip(vix_dates, vix_vals) if v and float(v) > 0]
    if vobs:
        store.upsert(vobs)
        sources["VIXCLS"] = "VIX réel (^VIX)"

    # Activité (ISM) ← tendance S&P 500 : momentum 6 mois (126 j) mappé autour de 50
    c = np.asarray(sp_closes, dtype=float)
    iobs = []
    for i in range(126, len(c)):
        if c[i - 126] <= 0:
            continue
        mom = c[i] / c[i - 126] - 1.0
        pmi = float(np.clip(50.0 + 100.0 * mom, 35.0, 65.0))   # +10 % / 6 mois → ~60 ; -10 % → ~40
        iobs.append(MacroObservation("ISM", _dt(sp_dates[i]), pmi, _dt(sp_dates[i])))
    if iobs:
        store.upsert(iobs)
        sources["ISM"] = "proxy tendance S&P 500 (réel)"

    is_real = bool(vobs or iobs)

    # FRED point-in-time (courbe des taux + chômage) — signaux de récession robustes
    if fred_key:
        try:
            from packages.regime.fred_provider import FredProvider
            fp = FredProvider(fred_key)
            for sid in ("T10Y2Y", "UNRATE"):
                try:
                    obs = fp.fetch(sid, vintages=True)
                    if obs:
                        store.upsert(obs)
                        sources[sid] = f"FRED {sid} (réel, point-in-time)"
                except Exception:  # noqa: BLE001 — série indispo → on continue
                    continue
        except Exception:  # noqa: BLE001
            pass

    return store, sources, is_real
