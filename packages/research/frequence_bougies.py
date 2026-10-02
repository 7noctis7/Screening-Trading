"""Un logit, un découpage, aucune grille. La sortie n'est une probabilité que si
la fréquence calibrée bat, sur le dernier bloc, la fréquence de base.
"""

from __future__ import annotations

import numpy as np

from packages.ml.calibration import PlattCalibrator, brier_score
from packages.ml.model import LogitModel
from packages.research.contrat_bougies import HORIZON, decision, seuil_brut

_PART_CAL = 0.70
_PART_TEST = 0.85
_MIN_LIGNES = 80


def _bornes(n: int) -> tuple[int, int] | None:
    """Train, calibration, test, avec un embargo d'un horizon entre chaque."""
    cal = int(n * _PART_CAL)
    test = int(n * _PART_TEST)
    if cal <= HORIZON or test <= cal + HORIZON or n - test < 15:
        return None
    return cal, test


def juger(X: np.ndarray, y: np.ndarray) -> dict:
    """AUC non publié comme probabilité. `calibre` ne vaut vrai que sur le test."""
    X, y = np.asarray(X, float), np.asarray(y, int)
    bornes = _bornes(len(y)) if len(y) >= _MIN_LIGNES else None
    if bornes is None or len(set(y.tolist())) < 2:
        return {"calibre": False, "motif": "échantillon trop court, ou une seule issue",
                "decision": "abstention", "seuil": round(seuil_brut(), 4)}
    cal, test = bornes
    modele = LogitModel().fit(X[:cal - HORIZON], y[:cal - HORIZON])
    brut_cal = modele.predict_proba(X[cal:test - HORIZON])
    y_cal = y[cal:test - HORIZON]
    if len(set(y_cal.tolist())) < 2:
        return {"calibre": False, "motif": "le bloc de calibration n'a qu'une issue",
                "decision": "abstention", "seuil": round(seuil_brut(), 4)}
    platt = PlattCalibrator().fit(brut_cal, y_cal)
    proba = np.asarray(platt.transform(modele.predict_proba(X[test:])), float)
    y_test = y[test:]
    base = float(y_test.mean())
    brier = brier_score(y_test, proba)
    brier_base = brier_score(y_test, np.full(len(y_test), base))
    calibre = brier < brier_base
    return {
        "calibre": calibre,
        "brier": brier,
        "brier_base": brier_base,
        "frequence_observee": round(base, 4),
        "seuil": round(seuil_brut(), 4),
        "n_test": int(len(y_test)),
        "decision": decision(float(np.nanmean(proba)), calibre),
        "motif": (None if calibre
                  else "le calibrage ne bat pas la fréquence de base"),
    }
