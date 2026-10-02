"""Distribution nulle de l'AUC — labels permutés à l'intérieur de chaque date.

Une permutation globale détruit aussi le taux de hausse du jour. Le modèle battrait
alors la nulle en apprenant seulement « ce jour est haussier », pas le classement
des titres. Permuter dans la date conserve ce taux et casse le lien feature → label.

Compteurs (convention du dépôt) :
* ``dates_melangees`` — dates d'au moins deux lignes, réellement permutables ;
* ``dates_figees`` — une seule ligne : la permutation ne peut rien faire ;
* ``dates_contrastables`` — permutables ET aux labels non tous identiques.
Zéro date contrastable : le garde-fou est actif mais ne teste rien. On ne rend
alors aucune AUC nulle, et l'edge reste UNCALIBRATED.
"""

from __future__ import annotations

import numpy as np

N_NULLES = 20


def _bornes(dates: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    order = np.argsort(dates, kind="mergesort")
    triees = dates[order]
    if len(order) == 0:
        return order, np.array([0])
    sauts = np.flatnonzero(triees[1:] != triees[:-1]) + 1
    return order, np.concatenate([[0], sauts, [len(order)]])


def compter_dates(y, dates) -> tuple[int, int, int]:
    """(mélangées, figées, contrastables)."""
    y = np.asarray(y)
    order, bornes = _bornes(np.asarray(dates))
    melangees = figees = contrastables = 0
    for a, b in zip(bornes[:-1], bornes[1:]):
        if b - a < 2:
            figees += 1
            continue
        melangees += 1
        if np.unique(y[order[a:b]]).size >= 2:
            contrastables += 1
    return melangees, figees, contrastables


def permuter_par_date(y, dates, rng) -> np.ndarray:
    """Copie de ``y`` dont les labels sont mélangés à l'intérieur de chaque date."""
    y = np.asarray(y).copy()
    order, bornes = _bornes(np.asarray(dates))
    for a, b in zip(bornes[:-1], bornes[1:]):
        if b - a < 2:
            continue
        idx = order[a:b]
        y[idx] = rng.permutation(y[idx])
    return y


def evaluer_plis(X, y_perm, plis, ajuster, auc) -> list[float]:
    """AUC de chaque pli sur des labels permutés. Les plis sont ceux du modèle réel."""
    notes = []
    for tr, te in plis:
        if np.unique(y_perm[tr]).size < 2 or np.unique(y_perm[te]).size < 2:
            continue
        note = auc(ajuster(X[tr], y_perm[tr], X[te]), y_perm[te])
        if note is not None and np.isfinite(note):
            notes.append(float(note))
    return notes


def calculer_nulles(y, dates, evaluer, n: int = N_NULLES, graine: int = 7) -> dict:
    """``n`` AUC moyennes. ``evaluer(y_perm)`` rend les AUC des plis."""
    melangees, figees, contrastables = compter_dates(y, dates)
    base = {
        "dates_melangees": melangees, "dates_figees": figees,
        "dates_contrastables": contrastables, "n_demandees": n,
        "n_rendues": 0, "n_essais": 0, "auc_nulles": [],
    }
    if contrastables == 0:
        base["motif"] = (
            "0 date contrastable : la permutation intra-date ne change aucun "
            "label, le test ne peut pas établir un edge"
        )
        return base
    rng = np.random.default_rng(graine)
    aucs: list[float] = []
    essais = 0
    while len(aucs) < n and essais < n * 3:
        essais += 1
        plis = evaluer(permuter_par_date(y, dates, rng))
        if plis:
            aucs.append(round(float(np.mean(plis)), 6))
    base["auc_nulles"] = aucs
    base["n_rendues"] = len(aucs)
    base["n_essais"] = essais
    base["motif"] = f"{len(aucs)} AUC nulles, {contrastables} dates contrastables"
    return base


def servir_nulles(*, y, dates, evaluer, stockees, activer: bool,
                  n: int = N_NULLES, graine: int = 7) -> dict:
    """Calcule si ``activer``, sinon relit l'artefact. Jamais les deux.

    Clé absente (``source == absente``) = le garde-fou n'a pas tourné.
    ``dates_contrastables == 0`` = il a tourné et n'a rien pu permuter.
    """
    if activer:
        calculees = calculer_nulles(y, dates, evaluer, n=n, graine=graine)
        calculees["source"] = "entrainement"
        return calculees
    if isinstance(stockees, dict) and "auc_nulles" in stockees:
        return {**stockees, "source": "artefact"}
    return {
        "auc_nulles": None, "source": "absente",
        "motif": "distribution nulle non calculée — make train avec QUANT_ML_NULLES",
    }
