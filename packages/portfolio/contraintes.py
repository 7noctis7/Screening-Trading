"""Contraintes appliquées à une allocation — plafond, exposition, régime, et chemin d'exécution.

Extrait de `recommendation.py`, qui dépassait 400 lignes. Le regroupement n'est pas
qu'administratif : ces quatre fonctions partagent une propriété que le reste du fichier
n'a pas — elles ne CHOISISSENT rien, elles bornent ou ordonnent un choix déjà fait. Les
lire ensemble rend visible l'ORDRE dans lequel elles s'appliquent, qui est la moitié de
leur correction.
"""
from __future__ import annotations

import numpy as np


def _plafonner(poids: list[float], plafond: float) -> tuple[list[float], int, float]:
    """Projection sur le simplex sous plafond : (poids, nb de plafonds activés, effet moyen).

    Les poids excédentaires sont fixés au plafond et le reliquat redistribué au prorata,
    par itérations — un simple `min(w, cap)` suivi d'une renormalisation ferait ressortir
    au-dessus du plafond ce qu'on venait d'y ramener.
    """
    base = [max(0.0, float(v)) for v in poids]
    n = len(base)
    if n * plafond < 1 - 1e-9:                      # contrainte infaisable, on ne bricole pas
        return base, 0, 0.0
    sortie, actifs, reste = [0.0] * n, set(range(n)), 1.0
    while actifs:
        total = sum(base[i] for i in actifs)
        equi = reste / len(actifs)
        depasse = [i for i in actifs
                   if (reste * base[i] / total if total > 0 else equi) > plafond + 1e-9]
        if not depasse:
            for i in actifs:
                sortie[i] = reste * base[i] / total if total > 0 else equi
            break
        for i in depasse:
            sortie[i], reste = plafond, reste - plafond
            actifs.discard(i)
    actives = sum(1 for v in base if v > plafond + 1e-9)
    effet = (sum(abs(sortie[i] - base[i]) for i in range(n)) / n) if actives else 0.0
    return sortie, actives, effet


def contraindre(poids: list[float], covariance: np.ndarray, plafond: float,
                profil: dict | None, moderation: float = 1.0) -> dict:
    """Plafond de ligne PUIS exposition dictée par le budget de perte du profil.

    L'ORDRE compte et n'est pas arbitraire. Le plafond est une contrainte RELATIVE (aucune
    ligne au-dessus de x %) : il redistribue à somme constante. L'exposition est ABSOLUE
    (le portefeuille entier ne doit pas pouvoir baisser de plus que le budget déclaré) :
    elle se lit sur la volatilité des poids DÉFINITIFS. Faire l'inverse mesurerait la
    volatilité d'une allocation qui ne sera pas détenue.

    `maxDD ≈ 2.5 × vol` (`vol_target_from_drawdown`) : la même conversion que le
    dimensionnement de production, pas une seconde formule pour le même objet.
    """
    plafonnes, actives, effet = _plafonner(poids, plafond)
    vecteur = np.asarray(plafonnes, dtype=float)
    vol = float(np.sqrt(max(0.0, vecteur @ covariance @ vecteur)))
    sortie = {"poids": plafonnes, "vol_annuelle": vol, "exposition": 1.0, "cash": 0.0,
              "plafonds_actives": actives, "effet_moyen_plafond": effet,
              "budget_perte": None, "vol_cible": None}
    if not profil:
        return sortie
    from packages.portfolio.construction import vol_target_from_drawdown
    from packages.profile.investor import Profil, budget_perte
    budget = budget_perte(Profil(**profil))
    cible = vol_target_from_drawdown(budget)
    # La modération de régime s'applique APRÈS le budget de perte : elle ne peut que
    # resserrer une exposition déjà autorisée, jamais l'élargir (facteur ≤ 1).
    exposition = (1.0 if vol <= 0 else min(1.0, cible / vol)) * max(0.0, min(1.0, moderation))
    sortie |= {"poids": [w * exposition for w in plafonnes], "exposition": exposition,
               "cash": 1.0 - exposition, "budget_perte": budget, "vol_cible": cible,
               "vol_apres_exposition": vol * exposition}
    return sortie


def moderation_regime(regime: dict | None, ic: dict | None) -> dict:
    """Le régime macro module l'EXPOSITION, jamais le choix des titres — et seulement vers le bas.

    DEUX DÉCISIONS, toutes deux discutables, donc énoncées.

    *Pourquoi l'exposition et pas les poids.* Incliner les poids entre titres suppose de
    savoir QUI profitera du régime : c'est une prévision transversale, et rien ici ne la
    valide. Réduire l'exposition ne suppose que de savoir que le risque global est moins
    bien payé — une affirmation plus faible, donc plus soutenable.

    *Pourquoi seulement vers le bas.* La perte et le gain ne sont pas symétriques : se
    tromper en étant prudent coûte un rendement manqué, se tromper en étant agressif peut
    coûter la capacité à rester investi. Un régime favorable n'autorise donc AUCUNE
    augmentation d'exposition au-delà de ce que le profil permet déjà.

    L'amplitude suit `force_preuve` — la même règle que les inclinaisons de la page profil :
    proportionnelle à la force de la PREUVE, pas à celle du signal. Sans mesure, la force
    vaut 0 et la modération vaut exactement 1,0 : le câblage est actif et n'a aucun effet
    tant que rien n'est démontré. C'est voulu.
    """
    from packages.profile.tilts import AMPLITUDE_MAX, force_preuve, vues_depuis_regime
    cycle = (regime or {}).get("cycle")
    risk_mode = (regime or {}).get("risk_mode")
    vues = vues_depuis_regime(cycle, risk_mode)
    # La preuve disponible est celle du score : c'est la seule mesurée dans ce dépôt. Le
    # régime lui-même n'a pas de t-stat publié — l'absence se dit, elle ne se remplace pas.
    preuve = force_preuve((ic or {}).get("t_stat"), (ic or {}).get("n_dates"))
    penchant = float(vues.get("actions_dev", 0.0))
    if penchant >= 0 or preuve["force"] <= 0:
        return {"facteur": 1.0, "cycle": cycle, "risk_mode": risk_mode,
                "force_preuve": preuve["force"], "motif": preuve["motif"] if penchant < 0
                else "régime non défensif — aucune réduction d'exposition",
                "reduction": 0.0}
    reduction = AMPLITUDE_MAX * preuve["force"] * min(1.0, abs(penchant))
    return {"facteur": 1.0 - reduction, "cycle": cycle, "risk_mode": risk_mode,
            "force_preuve": preuve["force"], "reduction": reduction,
            "motif": f"régime défensif ({cycle or 'n/d'} · {risk_mode or 'n/d'}), preuve "
                     f"{preuve['force']:.2f} → exposition réduite de {reduction:.1%}"}


def chemin_de_moindre_effort(covariance: np.ndarray, symboles: list[str],
                             actuel: dict[str, float], cible: dict[str, float]) -> list[dict]:
    """Ordonne les mouvements par variance évitée PAR POINT DE TURNOVER.

    « Voici la cible » n'est pas actionnable quand le turnover est de 100 % : le coût est
    certain et immédiat, le bénéfice diffus. La question utile est « quels mouvements
    achètent le plus de réduction de risque par euro échangé », et elle a une réponse
    exacte, pas une opinion.

    Glouton assumé : à chaque étape on retient le mouvement de meilleur rapport, on
    l'applique, on recalcule. Ce n'est pas l'optimum global du sous-ensemble — le problème
    est combinatoire — mais l'ordre produit est celui qu'un opérateur suivrait, et chaque
    ligne publie la variance ATTEINTE, vérifiable.

    La trésorerie est le résidu implicite (1 − Σw) : elle ne contribue pas à la variance,
    donc un mouvement qui sort du marché apparaît naturellement comme réducteur.
    """
    def variance(poids: dict[str, float]) -> float:
        vecteur = np.asarray([poids.get(s, 0.0) for s in symboles], dtype=float)
        return float(vecteur @ covariance @ vecteur)

    courant = {s: float(actuel.get(s, 0.0)) for s in symboles}
    restants = {s for s in symboles if abs(cible.get(s, 0.0) - courant[s]) > 1e-6}
    depart = variance(courant)
    total = variance({s: float(cible.get(s, 0.0)) for s in symboles})
    etapes, turnover_cumule = [], 0.0
    while restants:
        meilleur, meilleur_gain = None, None
        for symbole in restants:
            essai = dict(courant, **{symbole: float(cible.get(symbole, 0.0))})
            cout = abs(essai[symbole] - courant[symbole])
            gain = (variance(courant) - variance(essai)) / cout if cout > 1e-12 else 0.0
            if meilleur_gain is None or gain > meilleur_gain:
                meilleur, meilleur_gain = symbole, gain
        cout = abs(float(cible.get(meilleur, 0.0)) - courant[meilleur])
        courant[meilleur] = float(cible.get(meilleur, 0.0))
        restants.discard(meilleur)
        turnover_cumule += cout / 2
        atteinte = variance(courant)
        part = ((depart - atteinte) / (depart - total)) if abs(depart - total) > 1e-12 else 1.0
        etapes.append({
            "symbol": meilleur, "de": round(float(actuel.get(meilleur, 0.0)), 6),
            "vers": round(float(cible.get(meilleur, 0.0)), 6),
            "turnover_cumule": round(turnover_cumule, 6),
            "vol_atteinte": round(float(np.sqrt(max(0.0, atteinte))), 6),
            "part_du_gain": round(float(part), 4),
        })
    return etapes
