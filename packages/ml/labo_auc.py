"""Banc des variantes pré-enregistrées : CV purgée sur 80 %, verdict sur les 20 % tenus
à l'écart, et une règle de décision écrite AVANT la mesure.

PROTOCOLE (fixé le 07/10, avant tout chiffre réel).
1. Les 20 % d'échantillons les plus récents (par début de label) sont mis de côté ;
   tout échantillon de développement dont le label déborde sur cette période est
   purgé.
2. Sur les 80 % : CV purgée à 5 plis, mêmes plis pour les quatre variantes. Par pli :
   AUC, IC de rang hebdomadaire (score vs rendement relatif), MDA par grappes.
3. Sur la période tenue à l'écart, UNE évaluation par variante : IC de rang
   hebdomadaire.
4. RÈGLE : une variante n'est RETENUE que si (a) son IC hebdomadaire moyen sur la
   période tenue à l'écart dépasse celui de V0, intervalle bootstrap à 95 % (blocs de
   semaines) entièrement positif, ET (b) son propre t est > 2 sur des semaines
   disjointes. Sinon : rien ne change. Retenue ≠ adoptée : l'adoption est une PR à
   part, flag éteint par défaut, et quatre essais sont comptés au registre.

L'IC hebdomadaire se calcule sur toutes les semaines, mais son t se calcule sur des
semaines DISJOINTES (un label de 21 séances chevauche 4 semaines : sans cela le t
serait gonflé d'environ √4).
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np

from packages.ml.variantes_auc import VARIANTES, rendement_relatif, semaine, variante

PART_ECART = 0.20
N_PLIS = 5
MIN_PAR_SEMAINE = 20
N_BOOT = 2000


def ic_hebdo(score, rel, T0) -> dict:
    """IC de rang par semaine (≥ 20 titres) : {semaine: IC}."""
    import pandas as pd
    df = pd.DataFrame({"s": score, "r": rel, "w": semaine(T0)})
    out = {}
    for w, g in df.groupby("w"):
        if len(g) >= MIN_PAR_SEMAINE and g["s"].nunique() > 1:
            out[int(w)] = float(g["s"].rank().corr(g["r"].rank()))
    return out


def resume_ic(ics: dict, pas: int) -> dict:
    """Moyenne sur toutes les semaines ; t sur une semaine toutes les `pas`."""
    if not ics:
        return {"ic": None, "t": None, "n_semaines": 0}
    cles = sorted(ics)
    v = np.array([ics[k] for k in cles])
    disj = np.array([ics[k] for k in cles[::max(1, pas)]])
    sd = disj.std(ddof=1) if disj.size > 2 else 0.0
    t = float(disj.mean() / sd * np.sqrt(disj.size)) if sd > 0 else None
    return {"ic": float(v.mean()), "t": t, "n_semaines": int(v.size),
            "n_disjointes": int(disj.size)}


def bootstrap_ecart(a: dict, b: dict, pas: int, graine: int = 0) -> list | None:
    """IC à 95 % de mean(a − b) sur les semaines communes, blocs de `pas` semaines."""
    cles = sorted(set(a) & set(b))
    if len(cles) < 3 * max(1, pas):
        return None
    d = np.array([a[k] - b[k] for k in cles])
    rng, n, bloc = np.random.default_rng(graine), len(d), max(1, pas)
    moy = []
    for _ in range(N_BOOT):
        debuts = rng.integers(0, n - bloc + 1, size=int(np.ceil(n / bloc)))
        moy.append(np.concatenate([d[s:s + bloc] for s in debuts])[:n].mean())
    return [float(np.quantile(moy, 0.025)), float(np.quantile(moy, 0.975))]


def decouper(jeu: dict) -> tuple[np.ndarray, np.ndarray]:
    """(masque développement, masque tenu à l'écart), avec purge à la frontière."""
    debut, fin = jeu["T0"], jeu["T1"]
    frontiere = np.quantile(debut, 1 - PART_ECART)
    ecart = debut >= frontiere
    return (~ecart) & (fin < frontiere), ecart


def _cv(X, y, rel, T0, T1, fabrique: Callable, noms: list[str]) -> dict:
    from packages.ml.edge_transversal import auc
    from packages.ml.importance_mda import _perte_par_grappe, _plis, _resumer, grappes
    gr, rng = grappes(X), np.random.default_rng(0)
    aucs, ics, pertes = [], {}, []
    for tr, te in _plis(T0, T1, N_PLIS):
        if len(tr) < 100 or len(te) < 30 or len(set(y[te])) < 2:
            continue
        m = fabrique()
        m.fit(X[tr], y[tr])
        p = m.predict_proba(X[te])
        a = auc(p, y[te])
        if a is not None:
            aucs.append(a)
            pertes.append(_perte_par_grappe(m, X[te], y[te], a, gr, rng))
        ics.update(ic_hebdo(p, rel[te], T0[te]))
    mda = _resumer(gr, np.asarray(pertes, float))
    return {"auc_plis": aucs, "ics": ics,
            "mda": [{**g, "variables": [noms[i] for i in g["variables"]]} for g in mda]}


def evaluer_variante(nom: str, jeu: dict, fabrique: Callable, noms: list[str]) -> dict:
    X, y = variante(nom, jeu)
    rel = rendement_relatif(jeu["R"], jeu["T0"])
    dev, ecart = decouper(jeu)
    pas = int(np.ceil((jeu["h"] + 1) / 5))
    cv = _cv(X[dev], y[dev], rel[dev], jeu["T0"][dev], jeu["T1"][dev], fabrique, noms)
    m = fabrique()
    m.fit(X[dev], y[dev])
    ics_ecart = ic_hebdo(m.predict_proba(X[ecart]), rel[ecart], jeu["T0"][ecart])
    a = cv["auc_plis"]
    return {"variante": nom, "taux_positifs": float(y.mean()),
            "auc_cv": float(np.mean(a)) if a else None,
            "auc_cv_sd": float(np.std(a, ddof=1)) if len(a) > 1 else None,
            "ic_cv": resume_ic(cv["ics"], pas), "mda": cv["mda"],
            "ic_ecart": resume_ic(ics_ecart, pas), "_ics_ecart": ics_ecart,
            "n_dev": int(dev.sum()), "n_ecart": int(ecart.sum())}


def banc(jeu: dict, fabrique: Callable, noms: list[str]) -> dict:
    """Les quatre variantes, puis la règle de décision appliquée à chacune contre V0."""
    res = [evaluer_variante(v, jeu, fabrique, noms) for v in VARIANTES]
    pas = int(np.ceil((jeu["h"] + 1) / 5))
    base = res[0]["_ics_ecart"]
    for r in res:
        r["ecart_vs_v0_ic95"] = (None if r["variante"] == VARIANTES[0]
                                 else bootstrap_ecart(r["_ics_ecart"], base, pas))
        iv, t = r["ecart_vs_v0_ic95"], r["ic_ecart"]["t"]
        r["retenue"] = bool(iv and iv[0] > 0 and t is not None and t > 2)
        del r["_ics_ecart"]
    return {"variantes": res, "n_essais": len(VARIANTES),
            "retenues": [r["variante"] for r in res if r["retenue"]]}
