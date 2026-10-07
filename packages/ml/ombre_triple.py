"""Triple barrière + nulle hebdomadaire. SHADOW : aucun ordre, aucun snapshot.

Le score servi par l'onglet ML garde son label relatif. Ce module répond à une
autre question, pré-enregistrée et non branchée : la première barrière touchée
(profit / stop / temps), puis le méta-label « ce sens aurait-il payé les frais ».

La nulle permute CE méta-label à l'intérieur de chaque semaine. Moins de 20
tirages, ou le gel d'IC non levé : UNCALIBRATED, jamais « edge ».
"""

from __future__ import annotations

import numpy as np

STATUT = "SHADOW_UNCALIBRATED"
N_NULLES_MIN = 20


def _auc(scores, y) -> float | None:
    y = np.asarray(y, float)[np.argsort(scores)]
    n_pos, n = float(y.sum()), len(y)
    n_neg = n - n_pos
    if n_pos == 0 or n_neg == 0:
        return None
    ranks = np.arange(1, n + 1)
    return float((ranks[y == 1].sum() - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg))


def meta_labels(close: np.ndarray, entries: list[int], cout: float) -> list[dict]:
    """Méta-label du momentum 20 séances : 1 si le trade paie `cout` après barrières."""
    from packages.ml.labeling import ewm_volatility, triple_barrier
    vol = ewm_volatility(np.asarray(close, float))
    out = []
    for lab in triple_barrier(np.asarray(close, float), entries, pt=2.0, sl=2.0,
                              vol=vol, horizon=20):
        i = lab.entry_idx
        if i < 20:
            continue
        sens = 1 if close[i] >= close[i - 20] else -1
        out.append({"entry": i, "ret": lab.ret, "sens": sens,
                    "y": 1 if lab.ret * sens > cout else 0,
                    "score": float(close[i] / close[i - 20] - 1.0)})
    return out


def _permuter(y: np.ndarray, semaines: np.ndarray, rng) -> np.ndarray:
    out = y.copy()
    for w in np.unique(semaines):
        idx = np.flatnonzero(semaines == w)
        out[idx] = rng.permutation(y[idx])
    return out


def nulle_par_semaine(y, scores, semaines, n: int = N_NULLES_MIN,
                      graine: int = 0) -> list[float]:
    """AUC du score figé contre des méta-labels permutés dans chaque semaine."""
    y = np.asarray(y, float)
    sem = np.asarray(semaines)
    rng = np.random.default_rng(graine)
    aucs = []
    for _ in range(n):
        a = _auc(scores, _permuter(y, sem, rng))
        if a is not None:
            aucs.append(a)
    return aucs


def juger(y, scores, semaines, n: int = N_NULLES_MIN, graine: int = 0) -> dict:
    """Edge seulement si l'AUC observée bat la nulle (p < 5 %, ≥ 20 tirages)."""
    obs = _auc(scores, y)
    nul = nulle_par_semaine(y, scores, semaines, n=n, graine=graine)
    if obs is None or len(nul) < N_NULLES_MIN:
        return {"statut": "UNCALIBRATED", "edge": False, "auc": obs,
                "n_nulles": len(nul),
                "motif": "nulle insuffisante ou une seule classe"}
    arr = np.asarray(nul, float)
    p = float((1 + (arr >= obs).sum()) / (1 + arr.size))
    ok = p < 0.05 and obs > 0.5
    return {"statut": "MESURÉ", "edge": bool(ok), "auc": obs,
            "p_permutation": p, "n_nulles": int(arr.size),
            "motif": "p < 5 %" if ok else "indiscernable de la nulle hebdomadaire"}
