"""Détection de dérive (drift) — Population Stability Index (PSI).

PSI compare la distribution d'une feature entre une période de RÉFÉRENCE (train) et la
période COURANTE (live). PSI < 0.1 stable · 0.1–0.25 dérive modérée · > 0.25 dérive forte
→ déclenche un réentraînement. Pur numpy, testable.
"""

from __future__ import annotations

import numpy as np


def psi(reference, current, bins: int = 10) -> float:
    ref = np.asarray(reference, float)
    cur = np.asarray(current, float)
    ref = ref[~np.isnan(ref)]
    cur = cur[~np.isnan(cur)]
    if ref.size < 2 or cur.size < 2:
        return 0.0
    edges = np.quantile(ref, np.linspace(0, 1, bins + 1))
    edges[0], edges[-1] = -np.inf, np.inf
    r, _ = np.histogram(ref, bins=edges)
    c, _ = np.histogram(cur, bins=edges)
    rp = np.clip(r / r.sum(), 1e-6, None)
    cp = np.clip(c / c.sum(), 1e-6, None)
    return float(np.sum((cp - rp) * np.log(cp / rp)))


def drift_status(value: float) -> str:
    return "stable" if value < 0.1 else ("modéré" if value < 0.25 else "fort")


def feature_drift(ref_matrix, cur_matrix, names: list[str], bins: int = 10) -> dict:
    """PSI par feature + statut + drapeau global (au moins une dérive forte)."""
    ref = np.asarray(ref_matrix, float)
    cur = np.asarray(cur_matrix, float)
    out = {}
    for j, name in enumerate(names):
        p = psi(ref[:, j], cur[:, j], bins)
        out[name] = {"psi": round(p, 4), "status": drift_status(p)}
    flagged = [n for n, d in out.items() if d["status"] == "fort"]
    return {"by_feature": out, "drift_detected": bool(flagged), "flagged": flagged}
