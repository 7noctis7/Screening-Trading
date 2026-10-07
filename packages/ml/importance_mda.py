"""Importance MDA par GRAPPES, hors échantillon, sous validation croisée purgée.

POURQUOI. L'importance native d'un Gradient Boosting (MDI) se mesure SUR LE JEU
D'ENTRAÎNEMENT : elle récompense une variable que l'arbre a beaucoup utilisée, même
pour apprendre du bruit. Elle ne dit pas ce qui tient hors échantillon. Le MDA (Mean
Decrease Accuracy, López de Prado, AFML ch. 8) mesure, pli par pli et HORS
échantillon, combien l'AUC perd quand on brouille une variable.

POURQUOI DES GRAPPES. Deux variables corrélées (momentum 3 mois et momentum ajusté du
risque) se substituent l'une à l'autre : brouillées séparément, chacune paraît inutile
puisque l'autre porte la même information. On les regroupe (|corrélation de rang| ≥
seuil, liaison simple) et on brouille la grappe ENTIÈRE avec la même permutation.

LECTURE. `mda` > 0 avec t > 2 : la grappe porte de l'information hors échantillon.
`mda` ≈ 0 : brouiller ne change rien — la grappe n'apporte rien au modèle. Retirer des
variables sur cette base puis réévaluer sur les MÊMES données est une sélection : le
nouveau score doit être jugé sur une période tenue à l'écart, et compté au registre.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np

SEUIL_GRAPPE = 0.7


def _rangs(X: np.ndarray) -> np.ndarray:
    return np.argsort(np.argsort(X, axis=0), axis=0).astype(float)


def grappes(X: np.ndarray, seuil: float = SEUIL_GRAPPE) -> list[list[int]]:
    """Grappes de colonnes dont |corrélation de rang| ≥ seuil (liaison simple)."""
    k = X.shape[1]
    c = np.corrcoef(_rangs(X), rowvar=False) if len(X) > 2 else np.eye(k)
    parent = list(range(k))

    def racine(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(k):
        for j in range(i + 1, k):
            if np.isfinite(c[i, j]) and abs(c[i, j]) >= seuil:
                parent[racine(j)] = racine(i)
    groupes: dict[int, list[int]] = {}
    for i in range(k):
        groupes.setdefault(racine(i), []).append(i)
    return sorted(groupes.values())


def _plis(T0, T1, n_splits: int):
    from packages.ml.cv import PurgedKFold
    return list(PurgedKFold(n_splits=n_splits, embargo_pct=0.01).split(T0, T1))


def _perte_par_grappe(m, X_te, y_te, base: float, gr: list[list[int]],
                      rng: np.random.Generator) -> list[float]:
    from packages.ml.edge_transversal import auc
    pertes = []
    for g in gr:
        Xp = X_te.copy()
        perm = rng.permutation(len(Xp))
        Xp[:, g] = Xp[perm][:, g]                  # même permutation pour la grappe
        a = auc(m.predict_proba(Xp), y_te)
        pertes.append(base - a if a is not None else np.nan)
    return pertes


def mda_purge(X, y, T0, T1, fabrique: Callable, *, gr: list[list[int]] | None = None,
              n_splits: int = 5, graine: int = 0) -> dict:
    """MDA hors échantillon par grappe. `fabrique()` rend un modèle neuf (fit /
    predict_proba). Rend {grappes: [{variables, mda, se, t, n_plis}], auc_plis}."""
    from packages.ml.edge_transversal import auc
    X, y = np.asarray(X, float), np.asarray(y, float)
    gr = gr if gr is not None else grappes(X)
    rng = np.random.default_rng(graine)
    pertes, bases = [], []
    for tr, te in _plis(T0, T1, n_splits):
        if len(tr) < 100 or len(te) < 30 or len(set(y[te])) < 2:
            continue
        m = fabrique()
        m.fit(X[tr], y[tr])
        base = auc(m.predict_proba(X[te]), y[te])
        if base is None:
            continue
        bases.append(base)
        pertes.append(_perte_par_grappe(m, X[te], y[te], base, gr, rng))
    return {"grappes": _resumer(gr, np.asarray(pertes, float)), "auc_plis": bases}


def _resumer(gr: list[list[int]], P: np.ndarray) -> list[dict]:
    out = []
    for j, g in enumerate(gr):
        v = P[:, j][np.isfinite(P[:, j])] if P.size else np.array([])
        moy = float(v.mean()) if v.size else None
        se = float(v.std(ddof=1) / np.sqrt(v.size)) if v.size > 1 else None
        out.append({"variables": g, "mda": moy, "se": se, "n_plis": int(v.size),
                    "t": (moy / se) if (moy is not None and se) else None})
    return sorted(out, key=lambda d: -(d["mda"] if d["mda"] is not None else -9))


def nommer(resultat: dict, noms: list[str]) -> list[dict]:
    """Remplace les indices de colonnes par les noms des variables."""
    return [{**g, "variables": [noms[i] for i in g["variables"]]}
            for g in resultat["grappes"]]
