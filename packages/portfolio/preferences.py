"""Préférences sectorielles — des CONTRAINTES dont on mesure le coût, jamais des vues.

LA DISTINCTION QUI GOUVERNE CE MODULE. « Je veux privilégier la santé » peut vouloir dire
deux choses. Soit « je crois que la santé va surperformer » — une prévision, et rien ici ne
la valide (IC du score : +0,0202, t = 0,76). Soit « je veux au moins x % de mon portefeuille
en santé, pour des raisons qui m'appartiennent » — une contrainte, parfaitement légitime et
qui n'exige aucune preuve.

On implémente la seconde. Une exclusion, elle, ne demande aucune justification : refuser un
secteur est une décision personnelle, pas un pari.

CE QUI EST RENDU AVEC LE RÉSULTAT : le COÛT de la contrainte. Imposer un plancher détourne
du poids d'une allocation qui minimisait le risque ; la volatilité monte, la diversification
baisse. Ne pas afficher ce prix laisserait croire qu'une préférence est gratuite.
"""
from __future__ import annotations

import numpy as np


def _repartir(poids: np.ndarray, indices: list[int], cible: float) -> np.ndarray:
    """Porte la somme du groupe `indices` à `cible`, en puisant au prorata sur le reste."""
    sortie = poids.astype(float).copy()
    groupe = sortie[indices].sum()
    autres = [i for i in range(len(sortie)) if i not in set(indices)]
    reste = sortie[autres].sum()
    # UN PLANCHER NE CRÉE PAS UNE POSITION À PARTIR DE RIEN. Si l'optimiseur n'a donné
    # aucun poids au groupe, le monter au prorata est impossible et le monter à parts
    # égales reviendrait à inventer des lignes que le modèle de risque a refusées — et,
    # pire, à ressusciter un secteur qu'on venait d'exclure (trouvé par test le 07/09).
    # On ne satisfait pas le plancher, et l'appelant le DIT à l'utilisateur.
    if not indices or reste <= 0 or groupe <= 0 or groupe >= cible - 1e-12:
        return sortie
    manque = cible - groupe
    if manque > reste:                       # impossible sans vider les autres
        manque = reste
    # Le groupe monte au prorata de ses poids ACTUELS — un membre nul le reste, sinon on
    # inventerait une position que l'optimiseur n'a pas voulue.
    base = sortie[indices]
    sortie[indices] = base + manque * (base / groupe)
    sortie[autres] = sortie[autres] * (1.0 - manque / reste)
    return sortie


def appliquer(poids, secteurs: list[str], preferences: dict | None) -> dict:
    """Applique exclusions puis planchers/plafonds sectoriels, et rend le coût mesuré.

    ORDRE : exclure d'abord (une exclusion est absolue), puis les planchers, puis les
    plafonds. L'inverse laisserait un plancher réintroduire du poids sur un secteur exclu.
    """
    w = np.asarray(poids, dtype=float)
    vide = {"poids": list(w), "exclus": [], "planchers": [], "plafonds": [],
            "non_satisfaits": [], "applique": False}
    if not preferences or w.size == 0:
        return vide
    exclus = {s.strip().lower() for s in (preferences.get("exclure") or []) if s.strip()}
    planchers = {k.strip().lower(): float(v) for k, v in (preferences.get("planchers") or {}).items()}
    plafonds = {k.strip().lower(): float(v) for k, v in (preferences.get("plafonds") or {}).items()}
    if not (exclus or planchers or plafonds):
        return vide
    bas = [str(s or "").lower() for s in secteurs]
    journal: dict[str, list] = {"exclus": [], "planchers": [], "plafonds": [],
                                "non_satisfaits": []}

    if exclus:
        touches = [i for i, s in enumerate(bas) if s in exclus]
        retire = float(w[touches].sum())
        if retire > 0 and retire < 1.0 - 1e-9:
            w[touches] = 0.0
            w = w / w.sum()
            journal["exclus"] = [{"secteur": s, "poids_retire": retire} for s in sorted(exclus)]

    for secteur, mini in sorted(planchers.items()):
        if secteur in exclus:                     # une exclusion est ABSOLUE : elle prime
            journal["non_satisfaits"].append(
                {"secteur": secteur, "demande": mini,
                 "raison": "secteur exclu par ailleurs — l'exclusion prime sur le plancher"})
            continue
        indices = [i for i, s in enumerate(bas) if s == secteur]
        avant = float(w[indices].sum()) if indices else 0.0
        if not indices or avant <= 0:
            journal["non_satisfaits"].append(
                {"secteur": secteur, "demande": mini,
                 "raison": ("aucune ligne de ce secteur dans la sélection retenue — un plancher "
                            "ne crée pas une position que le modèle de risque n'a pas voulue")})
            continue
        if avant < mini - 1e-9:
            w = _repartir(w, indices, mini)
            journal["planchers"].append({"secteur": secteur, "avant": avant,
                                         "apres": float(w[indices].sum()), "demande": mini})

    for secteur, maxi in sorted(plafonds.items()):
        indices = [i for i, s in enumerate(bas) if s == secteur]
        avant = float(w[indices].sum()) if indices else 0.0
        if indices and avant > maxi + 1e-9:
            exces = avant - maxi
            w[indices] = w[indices] * (maxi / avant)
            autres = [i for i in range(len(w)) if i not in set(indices)]
            somme_autres = float(w[autres].sum())
            if somme_autres > 0:
                w[autres] = w[autres] * (1.0 + exces / somme_autres)
            journal["plafonds"].append({"secteur": secteur, "avant": avant, "apres": maxi})

    return {"poids": list(w), "applique": any(journal.values()), **journal}


def cout_de_la_contrainte(avant, apres, covariance) -> dict:
    """Ce que la préférence COÛTE, en volatilité et en diversification.

    Une préférence sectorielle détourne du poids d'une allocation qui minimisait le risque.
    Le prix est petit ou grand selon les corrélations — il n'est jamais nul, et ne pas
    l'afficher reviendrait à présenter un arbitrage comme un choix sans conséquence.
    """
    from packages.portfolio.indicateurs import (
        positions_effectives,
        ratio_diversification,
    )
    cov = np.asarray(covariance, dtype=float)

    def vol(w):
        v = np.asarray(w, dtype=float)
        return float(np.sqrt(max(0.0, v @ cov @ v)))

    vol_avant, vol_apres = vol(avant), vol(apres)
    # « écart », pas « surcoût » : exclure un actif très volatil FAIT BAISSER la volatilité.
    # Nommer cette différence un surcoût laisserait croire qu'une contrainte dégrade
    # toujours le risque, ce qui est faux — elle dégrade l'objectif de l'optimiseur, ce qui
    # n'est pas la même chose. Le signe est rendu tel quel, à l'utilisateur de le lire.
    return {"vol_avant": vol_avant, "vol_apres": vol_apres,
            "ecart_vol": vol_apres - vol_avant,
            "diversification_avant": ratio_diversification(avant, cov),
            "diversification_apres": ratio_diversification(apres, cov),
            "positions_effectives_avant": positions_effectives(avant),
            "positions_effectives_apres": positions_effectives(apres)}
