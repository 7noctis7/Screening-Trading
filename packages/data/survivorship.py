"""Audit du BIAIS DU SURVIVANT + chargeur de titres délistés.

Un univers composé des seuls titres *encore cotés aujourd'hui* surestime les performances passées
(les faillis/délistés ont disparu). On expose : (1) un audit honnête de l'ampleur du biais ;
(2) un chargeur optionnel `data/delisted.csv` (colonnes : symbol,name,sector,delisted_on) pour
réintégrer les disparus dans les backtests longs. stdlib uniquement.
"""

from __future__ import annotations

import csv
import os
from datetime import date, datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT = _ROOT / "data" / "delisted.csv"
_SEED = _ROOT / "data" / "delisted_seed.csv"   # liste curée (délistés/faillis)


def _as_date(v: object) -> date | None:
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    try:
        return datetime.fromisoformat(str(v)[:10]).date()
    except (TypeError, ValueError):
        return None


def derive_delisted(last_bar_by_symbol: dict[str, object], *, asof: date,
                    stale_days: int = 60, names: dict[str, str] | None = None,
                    sectors: dict[str, str] | None = None) -> list[dict]:
    """Dérive (point-in-time) les titres probablement DÉLISTÉS : ceux dont la dernière barre est
    antérieure de plus de `stale_days` à `asof` (sortie de cote / halt prolongé). Heuristique libre
    et reproductible — pas de fuite future (n'utilise que des dates ≤ asof). stdlib pur."""
    names = names or {}
    sectors = sectors or {}
    out: list[dict] = []
    for sym, last in last_bar_by_symbol.items():
        d = _as_date(last)
        if d is None or d > asof:
            continue                                         # date absente ou future → on ignore
        if (asof - d).days > stale_days:
            out.append({"symbol": sym, "name": names.get(sym, ""),
                        "sector": sectors.get(sym, ""), "delisted_on": d.isoformat()})
    out.sort(key=lambda r: r["symbol"])
    return out


def write_delisted(rows: list[dict], path: str | Path | None = None) -> int:
    """Écrit/fusionne data/delisted.csv (clé = symbol ; écriture atomique). Renvoie le total écrit."""
    p = Path(path) if path else _DEFAULT
    merged = {r["symbol"]: r for r in load_delisted(p)}      # conserve l'existant
    for r in rows:
        merged[r["symbol"]] = r                              # la dérivation récente prime
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp.csv")
    with tmp.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["symbol", "name", "sector", "delisted_on"])
        w.writeheader()
        for r in sorted(merged.values(), key=lambda x: x["symbol"]):
            w.writerow({k: r.get(k, "") for k in ("symbol", "name", "sector", "delisted_on")})
    os.replace(tmp, p)
    return len(merged)


def _read_csv(p: Path) -> list[dict]:
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


def load_delisted(path: str | Path | None = None) -> list[dict]:
    """Titres délistés. Sur le chemin par défaut, FUSIONNE la seed curée versionnée
    (`delisted_seed.csv`) avec les détectés en local (`delisted.csv`) → coverage solide
    même sans base (CI). Un chemin explicite ne lit QUE ce fichier."""
    p = Path(path) if path else _DEFAULT
    rows = _read_csv(p)
    if path is None:                                  # défaut → ajoute la seed curée
        seen = {r["symbol"] for r in rows}
        rows += [r for r in _read_csv(_SEED) if r["symbol"] not in seen]
    return rows


def survivorship_audit(universe_symbols: list[str], delisted: list[dict] | None = None,
                       min_coverage: float = 0.05) -> dict:
    """Audit : ampleur du biais + statut. `min_coverage` = plancher de plausibilité ;
    en-dessous, la « correction » est jugée sous-échantillonnée."""
    dl = delisted if delisted is not None else load_delisted()
    n_active = len(set(universe_symbols))
    n_dl = len({d["symbol"] for d in dl})
    total = n_active + n_dl
    # Délisting réel ~3-5 %/an actions US → sur ~10 ans, coverage attendu >> quelques %.
    # En-dessous du plancher, la « correction » est un trompe-l'œil.
    corrected = n_dl > 0
    coverage = round(n_dl / total, 3) if total else 0.0
    undersampled = corrected and coverage < min_coverage
    if not corrected:
        severity = "ÉLEVÉ — univers survivant uniquement"
    elif undersampled:
        severity = "ÉLEVÉ — délistés SOUS-ÉCHANTILLONNÉS (coverage < seuil plausible)"
    else:
        severity = "corrigé (partiel)"
    return {
        "available": True,
        "corrected": corrected,
        "undersampled": undersampled,
        "n_active": n_active,
        "n_delisted": n_dl,
        "delisted_coverage": coverage,
        "min_coverage": min_coverage,
        "severity": severity,
        "bias_direction": "performances passées SURESTIMÉES (les disparus sont absents)",
        "note": ("Coverage trop faible → lancer `make ingest-delisted` sur la base "
                 "complète pour élargir data/delisted.csv." if undersampled else
                 "Biais corrigé partiellement via data/delisted.csv." if corrected else
                 "Pour corriger : déposer data/delisted.csv (symbol,name,sector,delisted_on) "
                 "avec les titres sortis de l'univers. Sinon, lire les backtests longs comme "
                 "optimistes."),
    }
