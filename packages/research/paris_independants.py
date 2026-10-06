"""Combien de paris INDÉPENDANTS le livre prend-il ? (IR ≈ IC × √N)

Vingt grandes capitalisations corrélées à 0,6 ne sont pas vingt paris. N, dans la loi
fondamentale de la gestion active, est le nombre de paris indépendants : le compter en
lignes surestime l'IR qu'un IC peut produire.

MESURE, à chaque décision : la matrice de corrélation des rendements quotidiens des noms
détenus sur les `fenetre` séances PRÉCÉDENTES (point-in-time), puis le nombre effectif
par le ratio de participation des valeurs propres :

    N_eff = (Σ λ)² / Σ λ²

N_eff = nombre de lignes si elles sont décorrélées, 1 si elles bougent toutes ensemble.
Par an : N_eff médian × (252 / détention médiane en séances), car un pari ne se
renouvelle qu'en changeant de position.
"""

from __future__ import annotations

import numpy as np

FENETRE = 120


def n_effectif(rendements: np.ndarray) -> float | None:
    """Ratio de participation des valeurs propres de corrélation (lignes : titres)."""
    r = np.asarray(rendements, float)
    if r.ndim != 2 or r.shape[0] < 2 or r.shape[1] < 20:
        return None
    sd = r.std(axis=1, ddof=1)
    r = r[sd > 0]
    if r.shape[0] < 2:
        return None
    lam = np.clip(np.linalg.eigvalsh(np.corrcoef(r)), 0.0, None)
    return float(lam.sum() ** 2 / (lam ** 2).sum()) if (lam ** 2).sum() > 0 else None


def _rendements_avant(prix: dict, syms: list, jour: str, fenetre: int) -> np.ndarray:
    """Rendements des `fenetre` séances communes ≤ jour (aucune date postérieure)."""
    jours = sorted(set.intersection(*[{j for j in prix[s] if j <= jour} for s in syms]))
    jours = jours[-(fenetre + 1):]
    if len(jours) < 21:
        return np.empty((0, 0))
    m = np.asarray([[prix[s][j] for j in jours] for s in syms], float)
    return m[:, 1:] / m[:, :-1] - 1.0


def par_decision(decisions: list, prix: dict, fenetre: int = FENETRE) -> list[dict]:
    """[{jour, n_lignes, n_eff}] pour chaque décision à au moins deux noms cotés."""
    out = []
    for jour, poids in decisions:
        syms = [s for s, w in (poids or {}).items() if w > 0 and s in prix]
        if len(syms) < 2:
            continue
        n_eff = n_effectif(_rendements_avant(prix, syms, jour, fenetre))
        if n_eff is not None:
            out.append({"jour": jour, "n_lignes": len(syms), "n_eff": n_eff})
    return out


def resume(lignes: list[dict], detention_mediane_seances: float | None) -> dict:
    if not lignes:
        return {"available": False, "status": "UNCALIBRATED"}
    n_eff = float(np.median([x["n_eff"] for x in lignes]))
    n_lig = float(np.median([x["n_lignes"] for x in lignes]))
    par_an = (n_eff * 252.0 / detention_mediane_seances
              if detention_mediane_seances and detention_mediane_seances > 0 else None)
    return {"available": True, "n_decisions": len(lignes), "n_lignes_median": n_lig,
            "n_eff_median": n_eff,
            "n_eff_p10_p90": [float(np.quantile([x["n_eff"] for x in lignes], q))
                              for q in (0.1, 0.9)],
            "detention_mediane_seances": detention_mediane_seances,
            "paris_independants_par_an": par_an}
