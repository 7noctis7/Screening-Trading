"""Ce que le gate PEUT détecter : Sharpe minimal et années nécessaires (puissance du DSR).

POURQUOI (10/11). Chaque verdict du dépôt dit « DSR ≈ 0, non établi ». Aucun ne dit ce
qu'il aurait FALLU pour être établi. Or le seuil du DSR monte avec le nombre d'essais du
registre et descend avec la longueur de l'historique : à 5 744 essais et 10 ans de barres
quotidiennes, il faut un Sharpe annualisé d'environ 1,7 pour sortir « déployable ». Un
effet réel plus petit (un classement long-only qui bat son univers de 3 %/an, IR ≈ 0,4)
est donc refusé PAR CONSTRUCTION, qu'il existe ou non. Un « non établi » sans son seuil
de détection ne distingue pas « il n'y a rien » de « l'instrument ne peut pas le voir ».

CE MODULE NE CHANGE AUCUN SEUIL ET NE JUGE RIEN. Il inverse la formule que le gate
applique déjà (`portfolio.psr.deflated_sharpe_ratio`, écart-type de Bailey √(1/n), le
défaut de `protocole_oos.porte_de_deploiement`) pour publier sa caractéristique de
fonctionnement. C'est de l'arithmétique sur le compteur réel du registre : aucun prix,
aucune calibration.

LIMITE. Rendements supposés normaux (skew 0, kurtosis 3) : des queues épaisses relèvent
le seuil. Les chiffres publiés sont donc un PLANCHER de ce qu'il faut.
"""
from __future__ import annotations

import math

from packages.portfolio.psr import deflated_sharpe_ratio
from packages.research.gate import DSR_MIN
from packages.research.protocole_oos import SEUIL_DSR

SEANCES_PAR_AN = 252
SEUILS = {"promouvable": DSR_MIN, "déployable": SEUIL_DSR}
_SHARPE_MAX = 2.0            # par séance : borne haute de la recherche (≈ 32 annualisé)


def sharpe_minimal(n_obs: int, n_essais: int, seuil: float = SEUIL_DSR) -> float | None:
    """Plus petit Sharpe PAR PÉRIODE dont le DSR dépasse `seuil`. None si inatteignable."""
    if n_obs < 2 or n_essais < 1 or not 0.0 < seuil < 1.0:
        return None
    if deflated_sharpe_ratio(_SHARPE_MAX, n_obs, n_essais) <= seuil:
        return None
    bas, haut = -_SHARPE_MAX, _SHARPE_MAX
    for _ in range(60):
        milieu = (bas + haut) / 2.0
        if deflated_sharpe_ratio(milieu, n_obs, n_essais) > seuil:
            haut = milieu
        else:
            bas = milieu
    return haut


def sharpe_annuel_minimal(annees: float, n_essais: int,
                          seuil: float = SEUIL_DSR) -> float | None:
    """Le même seuil, annualisé, pour `annees` de barres quotidiennes."""
    s = sharpe_minimal(int(round(annees * SEANCES_PAR_AN)), n_essais, seuil)
    return None if s is None else s * math.sqrt(SEANCES_PAR_AN)


def annees_necessaires(sharpe_annuel: float, n_essais: int, seuil: float = SEUIL_DSR,
                       maximum: float = 200.0) -> float | None:
    """Années de barres quotidiennes pour qu'un Sharpe annualisé VRAI passe la porte.

    None si même `maximum` années ne suffisent pas (ou si le Sharpe est ≤ 0)."""
    if sharpe_annuel <= 0:
        return None
    s_min = sharpe_annuel_minimal(maximum, n_essais, seuil)
    if s_min is None or s_min > sharpe_annuel:
        return None
    bas, haut = 1.0 / SEANCES_PAR_AN * 2, maximum
    for _ in range(60):
        milieu = (bas + haut) / 2.0
        s = sharpe_annuel_minimal(milieu, n_essais, seuil)
        if s is not None and s <= sharpe_annuel:
            haut = milieu
        else:
            bas = milieu
    return haut


def tableau(n_essais: int, annees: tuple[float, ...] = (3, 5, 10, 20),
            sharpes: tuple[float, ...] = (0.3, 0.5, 1.0, 1.5)) -> dict[str, object]:
    """Caractéristique du gate pour `n_essais` : seuils par durée, durées par Sharpe."""
    return {
        "n_essais": n_essais,
        "hypothese": "rendements normaux : plancher de ce qu'il faut",
        "sharpe_annuel_minimal": {
            nom: {a: sharpe_annuel_minimal(a, n_essais, s) for a in annees}
            for nom, s in SEUILS.items()},
        "annees_necessaires": {
            nom: {sh: annees_necessaires(sh, n_essais, s) for sh in sharpes}
            for nom, s in SEUILS.items()},
    }
