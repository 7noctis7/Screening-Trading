"""Validation de l'edge ML affiché — ce qui doit tenir sur du bruit (QML-011).

Trois briques, chacune corrige un défaut mesuré le 25/09 sur la section ML du snapshot :

* `bornes_label` : bornes du label en JOURS CALENDAIRES. La CV purgée recevait l'index
  positionnel de chaque série ; deux titres introduits à des dates différentes avaient le
  même `t` pour deux dates distinctes, et la purge ne purgeait pas le temps réel.
* `edge_detecte` : l'étiquette « edge » exige une p-valeur de PERMUTATION. Le plancher seul
  (0,52) passait 5 fois sur 10 sur une marche aléatoire pure ; sans distribution nulle,
  le statut est UNCALIBRATED.
* `calibration_hors_echantillon` : Platt ajusté sur une moitié, évalué sur l'autre. Le
  Brier « calibré » était mesuré là où Platt venait d'apprendre.

Mesure, pas décision : rien ici ne pilote un ordre (le ML reste de l'affichage).
"""

from __future__ import annotations

import numpy as np

PLANCHER_AUC = 0.52
PLIS_MIN = 3
N_NULLES_MIN = 20
ALPHA = 0.05


def bornes_label(bars: list, t: int, horizon: int) -> tuple[int, int]:
    """(début, fin) du label `bars[t] → bars[t+horizon]`, en ordinaux de jour calendaire."""
    return bars[t].ts.toordinal(), bars[t + horizon].ts.toordinal()


def edge_detecte(aucs: list[float], auc_nulles: list[float] | None = None,
                 plancher: float = PLANCHER_AUC, n_nulles_min: int = N_NULLES_MIN) -> dict:
    """Un edge ne s'affirme que contre une distribution NULLE (AUC de labels permutés).

    Mesuré le 25/09 sur marche aléatoire pure, 10 graines : le plancher seul (AUC ≥ 0,52)
    passait 5 fois, une borne basse sur la dispersion des plis encore 4 fois — les plis
    partagent le facteur de marché, leur dispersion sous-estime l'incertitude. Sans
    distribution nulle suffisante : UNCALIBRATED, jamais « edge »."""
    a = np.asarray([x for x in aucs if x is not None and np.isfinite(x)], float)
    base = {"auc_moyenne": round(float(a.mean()), 4) if a.size else None, "n_plis": int(a.size)}
    nul = np.asarray([x for x in (auc_nulles or []) if np.isfinite(x)], float)
    if a.size < PLIS_MIN or nul.size < n_nulles_min:
        return {**base, "edge": False, "statut": "UNCALIBRATED",
                "motif": (f"{nul.size} AUC nulle(s) < {n_nulles_min} : sans test de "
                          "permutation, l'AUC de CV ne se distingue pas du hasard")}
    moyenne = float(a.mean())
    p = float((1 + (nul >= moyenne).sum()) / (1 + nul.size))
    ok = p < ALPHA and moyenne >= plancher
    return {**base, "edge": bool(ok), "statut": "MESURÉ", "p_permutation": round(p, 4),
            "n_nulles": int(nul.size),
            "motif": "p de permutation < 5 %" if ok else "indiscernable de la distribution nulle"}


def calibration_hors_echantillon(p, y, bins: int = 8) -> dict:
    """Platt ajusté sur la 1re moitié (chronologique), Brier et fiabilité sur la 2de."""
    from packages.ml.calibration import PlattCalibrator, brier_score, reliability_curve
    p, y = np.asarray(p, float), np.asarray(y, float)
    mi = len(p) // 2
    if mi < 25 or len(p) - mi < 25:
        return {"available": False}
    cal = PlattCalibrator().fit(p[:mi], y[:mi])
    p_eval = cal.transform(p[mi:])
    return {"available": True, "brier_raw": brier_score(y[mi:], p[mi:]),
            "brier_calibrated": brier_score(y[mi:], p_eval),
            "reliability": reliability_curve(y[mi:], p_eval, bins=bins),
            "n_ajustement": mi, "n_evaluation": len(p) - mi}
