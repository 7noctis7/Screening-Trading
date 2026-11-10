"""Un classement CANDIDAT face au classement TÉMOIN : mêmes titres, mêmes dates.

POURQUOI (10/11). `ic_classement` mesure le classement de production contre ZÉRO. Un
candidat qui le remplacerait doit battre ce classement-là, pas le hasard : sinon tout
signal corrélé au momentum « passe » en héritant de son IC. La mesure est donc APPARIÉE :
à chaque date, l'IC du candidat moins celui du témoin, sur la même coupe transversale.
C'est aussi là qu'est la puissance statistique : la largeur de la coupe (des centaines de
titres par date) et non la courbe d'un seul portefeuille (cf. `puissance_gate`).

MÉTHODE. Clôtures alignées PAR DATE sur le calendrier commun. Score connu au close du jour
t ; cible = close(t + 1) → close(t + 1 + h), le prix d'exécution, jamais le close du
signal (même convention que `ic_classement`). Pas = h : fenêtres DISJOINTES. Nulle par
inversion de signe des écarts datés (ADR-0217 : elle porte la vraie variabilité d'une
date à l'autre). Un titre dont la fenêtre a un trou n'est pas classé ; son nombre est
publié.

STATUT : CANDIDATE. Module de recherche, aucun appelant en production.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np

from packages.ranking.momentum_residuel import (
    calendrier_commun,
    matrice_cloture,
    rendements_marche,
    scores_residuels,
)
from packages.research.ic_classement import (
    N_DATES_MIN,
    N_TITRES_MIN,
    TOP_K,
    _corr,
    _ecart_top,
    _rangs,
    nulle,
)

STATUT = "CANDIDATE"
Classement = Callable[[dict[str, Any], int], "np.ndarray | None"]


def panneau(data: dict[str, Any]) -> dict[str, Any]:
    """{jours, syms, C, R, m} : clôtures, rendements et marché alignés par date."""
    from packages.backtest.panel import _jour
    par_titre = {}
    for s, barres in data.items():
        cours = {_jour(b): float(b.close) for b in barres
                 if b.close is not None and b.close == b.close and b.close > 0}
        if cours:
            par_titre[s] = cours
    jours = calendrier_commun(par_titre)
    C, syms = matrice_cloture(par_titre, jours)
    R = np.full_like(C, np.nan)
    if len(jours) > 1:
        R[1:] = C[1:] / C[:-1] - 1.0
    return {"jours": jours, "syms": syms, "C": C, "R": R, "m": rendements_marche(R)}


def classement_residuel(estimation: int, formation: int, saut: int,
                        standardise: bool) -> Classement:
    """Score du plugin `momentum_residuel` au jour t (fenêtre de rendements ≤ t)."""
    def score(pan: dict[str, Any], t: int) -> np.ndarray | None:
        debut = t - estimation + 1
        if debut < 1:                       # la ligne 0 n'a pas de rendement
            return None
        return scores_residuels(pan["R"][debut:t + 1], pan["m"][debut:t + 1],
                                formation=formation, saut=saut, standardise=standardise)
    return score


def classement_momentum(fenetre: int = 252, saut: int = 21) -> Classement:
    """Le témoin : c[t − saut] / c[t − fenetre] − 1, coté aux deux bornes ET au jour t
    (un titre absent le jour de la décision ne peut pas être choisi ce jour-là)."""
    def score(pan: dict[str, Any], t: int) -> np.ndarray | None:
        if t - fenetre < 0:
            return None
        C = pan["C"]
        return np.where(np.isfinite(C[t]), C[t - saut] / C[t - fenetre] - 1.0, np.nan)
    return score


def classement_placebo(classement: Classement, graine: int) -> Classement:
    """Les MÊMES scores redistribués au hasard entre les titres classés : même coupe,
    même nombre de lignes, sélection sans information."""
    def score(pan: dict[str, Any], t: int) -> np.ndarray | None:
        sc = classement(pan, t)
        if sc is None:
            return None
        out = sc.copy()
        ok = np.flatnonzero(np.isfinite(sc))
        rng = np.random.default_rng(graine * 1_000_003 + t)
        out[ok] = sc[rng.permutation(ok)]
        return out
    return score


def lignes(pan: dict[str, Any], classement: Classement, h: int, pas: int,
           debut: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Une ligne par date mesurable (RankIC, écart du top-12) et les compteurs."""
    C, jours = pan["C"], pan["jours"]
    out: list[dict[str, Any]] = []
    sautees = 0
    for t in range(debut, len(jours) - h - 1, max(1, pas)):
        sc = classement(pan, t)
        if sc is None:
            sautees += 1
            continue
        fut = C[t + 1 + h] / C[t + 1] - 1.0
        ok = np.isfinite(sc) & np.isfinite(fut)
        ic = _corr(_rangs(sc[ok]), _rangs(fut[ok])) if ok.sum() >= N_TITRES_MIN else None
        if ic is None:
            sautees += 1
            continue
        out.append({"jour": jours[t], "ic": ic, "top": _ecart_top(sc[ok], fut[ok], TOP_K),
                    "n": int(ok.sum()), "ecartes": int((~np.isfinite(sc)).sum())})
    return out, {"dates_mesurees": len(out), "dates_sautees": sautees,
                 "titres_classes_mediane": _mediane([li["n"] for li in out]),
                 "titres_ecartes_mediane": _mediane([li["ecartes"] for li in out])}


def _mediane(x: list[int]) -> float | None:
    return float(np.median(x)) if x else None


def ecart_apparie(candidat: list[dict[str, Any]], temoin: list[dict[str, Any]],
                  n_nulles: int = 2000) -> dict[str, Any]:
    """IC(candidat) − IC(témoin) par date commune ; UNCALIBRATED sous `N_DATES_MIN`."""
    ref = {li["jour"]: li["ic"] for li in temoin}
    d = np.asarray([li["ic"] - ref[li["jour"]] for li in candidat if li["jour"] in ref])
    if d.size < N_DATES_MIN:
        return {"available": False, "status": "UNCALIBRATED", "n_dates": int(d.size)}
    nul = nulle(d, n_nulles)
    obs = float(d.mean())
    sd = float(d.std(ddof=1))
    m = d.size // 2
    return {"available": True, "status": "MESURÉ", "n_dates": int(d.size),
            "ecart_ic_moyen": obs,
            "t_stat": float(obs / sd * np.sqrt(d.size)) if sd > 0 else None,
            "p_signes": float((1 + (np.abs(nul) >= abs(obs) - 1e-12).sum())
                              / (1 + nul.size)),
            "part_positive": float((d > 0).mean()),
            "ecart_premiere_moitie": float(d[:m].mean()),
            "ecart_seconde_moitie": float(d[m:].mean())}
