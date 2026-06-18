"""Audit du BIAIS DU SURVIVANT + chargeur de titres délistés.

Un univers composé des seuls titres *encore cotés aujourd'hui* surestime les performances passées
(les faillis/délistés ont disparu). On expose : (1) un audit honnête de l'ampleur du biais ;
(2) un chargeur optionnel `data/delisted.csv` (colonnes : symbol,name,sector,delisted_on) pour
réintégrer les disparus dans les backtests longs. stdlib uniquement.
"""

from __future__ import annotations

import csv
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT = _ROOT / "data" / "delisted.csv"


def load_delisted(path: str | Path | None = None) -> list[dict]:
    """Lit la liste des titres délistés (vide si le fichier n'existe pas)."""
    p = Path(path) if path else _DEFAULT
    if not p.exists():
        return []
    out: list[dict] = []
    try:
        with p.open(encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row.get("symbol"):
                    out.append({"symbol": row["symbol"].strip(),
                                "name": (row.get("name") or "").strip(),
                                "sector": (row.get("sector") or "").strip(),
                                "delisted_on": (row.get("delisted_on") or "").strip()})
    except Exception:  # noqa: BLE001
        return []
    return out


def survivorship_audit(universe_symbols: list[str], delisted: list[dict] | None = None) -> dict:
    """Audit : ampleur estimée du biais + statut de correction (selon présence de `delisted.csv`)."""
    dl = delisted if delisted is not None else load_delisted()
    n_active = len(set(universe_symbols))
    n_dl = len({d["symbol"] for d in dl})
    total = n_active + n_dl
    # Taux de délisting réaliste : ~3-5 %/an sur actions US → sur ~10 ans, biais notable.
    corrected = n_dl > 0
    coverage = round(n_dl / total, 3) if total else 0.0
    return {
        "available": True,
        "corrected": corrected,
        "n_active": n_active,
        "n_delisted": n_dl,
        "delisted_coverage": coverage,
        "severity": "corrigé (partiel)" if corrected else "ÉLEVÉ — univers survivant uniquement",
        "bias_direction": "performances passées SURESTIMÉES (les disparus sont absents)",
        "note": ("Biais corrigé partiellement via data/delisted.csv." if corrected else
                 "Pour corriger : déposer data/delisted.csv (symbol,name,sector,delisted_on) "
                 "avec les titres sortis de l'univers. Sinon, lire les backtests longs comme "
                 "optimistes."),
    }
