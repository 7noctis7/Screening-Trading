"""Lignage & réconciliation de données (gouvernance, auditable, 0 dépendance).

Deux primitives indépendantes des providers :
1. `fingerprint()` — provenance d'une série (source, volumétrie, plage, SHA-256
   déterministe) → traçabilité point-in-time, sérialisable en `lineage.json`.
2. `reconcile()` — accord entre DEUX sources sur dates communes : divergence
   relative max/moyenne + brèches au-delà d'une tolérance. Détecte les désynchros
   silencieuses (yfinance vs FMP vs cache HF) avant corruption d'un backtest.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from datetime import UTC


@dataclass(frozen=True)
class Fingerprint:
    name: str
    source: str
    n_rows: int
    start: str | None
    end: str | None
    sha256: str

    def to_dict(self) -> dict:
        return asdict(self)


def fingerprint(
    name: str, source: str, dates: list[str], values: list[float]
) -> Fingerprint:
    """Empreinte déterministe d'une série (date, valeur). Hash invariant à l'ordre
    (mêmes données → même hash) → comparable entre runs et machines."""
    pairs = sorted(zip(dates, values, strict=False), key=lambda p: str(p[0]))
    h = hashlib.sha256()
    for d, v in pairs:
        h.update(f"{d}:{float(v):.10g}".encode())
    ds = [str(d) for d, _ in pairs]
    return Fingerprint(
        name=name, source=source, n_rows=len(pairs),
        start=ds[0] if ds else None, end=ds[-1] if ds else None,
        sha256=h.hexdigest(),
    )


def reconcile(
    series_a: dict[str, float],
    series_b: dict[str, float],
    tol: float = 0.005,
) -> dict:
    """Réconcilie deux séries {date: close}. Divergence relative sur dates communes :
        d_t = |a_t - b_t| / max(|a_t|, eps)
    Retourne max/mean de d_t, le nombre de dates au-delà de `tol`, et un verdict `ok`.
    `ok = False` signale une désynchro à investiguer (jamais bloquant en soi)."""
    common = sorted(set(series_a) & set(series_b))
    if not common:
        return {"n_overlap": 0, "max_rel_div": None, "mean_rel_div": None,
                "n_breaches": 0, "tol": tol, "ok": True}
    eps = 1e-12
    divs = []
    for d in common:
        a, b = float(series_a[d]), float(series_b[d])
        divs.append(abs(a - b) / max(abs(a), eps))
    breaches = sum(1 for x in divs if x > tol)
    return {
        "n_overlap": len(common),
        "max_rel_div": round(max(divs), 6),
        "mean_rel_div": round(sum(divs) / len(divs), 6),
        "n_breaches": breaches,
        "tol": tol,
        "ok": breaches == 0,
    }


def write_manifest(entries: list[Fingerprint | dict], path) -> None:
    """Écrit le manifeste de lignage (JSON) — best-effort, jamais bloquant."""
    import json
    from datetime import datetime
    try:
        payload = {
            "generated_at": datetime.now(UTC).isoformat(),
            "entries": [e.to_dict() if isinstance(e, Fingerprint) else e
                        for e in entries],
        }
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
    except OSError:
        pass
