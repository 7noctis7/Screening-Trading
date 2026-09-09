"""Le profil « Conviction » — le seul qui utilise un rendement attendu, donc le seul
qu'une mesure a le droit d'interdire.

Isolé de `recommendation.py` pour deux raisons. La première est mécanique : le fichier
dépassait 400 lignes. La seconde compte davantage — tout ce qui touche à un rendement
ATTENDU doit être lisible d'un seul tenant, avec ses garde-fous sous les yeux, plutôt que
dispersé au milieu de calculs de risque qui, eux, ne prétendent rien prédire.
"""
from __future__ import annotations

import numpy as np


def somers_d(auc: float | None) -> float | None:
    """AUC → coefficient d'information équivalent : D = 2·AUC − 1.

    Un classifieur binaire et un score continu ne se comparent pas directement ; le D de
    Somers est la passerelle standard, et c'est exactement une corrélation de rangs. Elle
    rend aussi visible ce que l'affichage « edge détecté » masque : un AUC de 0,52, c'est
    un IC de 0,04. Utilisable, minuscule — et l'amplitude des vues le reflétera.
    """
    if auc is None:
        return None
    return 2.0 * float(auc) - 1.0


def _z(valeurs: list[float]) -> np.ndarray:
    serie = np.asarray(valeurs, dtype=float)
    ecart = float(np.nanstd(serie))
    return (serie - float(np.nanmean(serie))) / (ecart if ecart > 1e-12 else 1.0)


def vues_combinees(scores: list[float], ml: list[float | None] | None,
                   ic_score: float, ic_ml: float | None) -> tuple[np.ndarray, float]:
    """Combine deux signaux en pondérant chacun par SON coefficient d'information.

    Un signal à IC 0,04 et un signal à IC 0,12 ne pèsent pas pareil : les additionner à
    poids égaux reviendrait à prêter au plus faible une force qu'il n'a pas. La pondération
    par l'IC est la solution de moindre variance quand les signaux sont peu corrélés — et
    elle a la propriété qui nous intéresse ici : un signal nul disparaît de lui-même.

    Renvoie (z combiné, IC combiné). Sans ML exploitable, on retombe exactement sur le
    score seul — aucune branche particulière, donc aucun comportement à part à maintenir.
    """
    z_score = _z(scores)
    if not ml or ic_ml is None or abs(ic_ml) <= 1e-9:
        return z_score, abs(ic_score)
    remplis = [v if v is not None else float("nan") for v in ml]
    z_ml = np.nan_to_num(_z(remplis), nan=0.0)
    poids_total = abs(ic_score) + abs(ic_ml)
    combine = (abs(ic_score) * z_score + abs(ic_ml) * z_ml) / poids_total
    # IC d'une combinaison de signaux INDÉPENDANTS : √(Σ IC²). Hypothèse optimiste et
    # assumée — deux signaux corrélés font moins. On la borne donc par la somme simple.
    return combine, float(min(poids_total, np.hypot(ic_score, ic_ml)))


def scenario_conviction(covariance: np.ndarray, scores: list[float], ic: dict | None,
                        ml_scores: list[float | None] | None = None,
                        ml_auc: float | None = None) -> tuple[list | None, str]:
    """Black-Litterman : prior = ERC, vues = signaux calibrés par leur IC MESURÉ.

    L'amplitude des vues vaut IC × σ × z (Grinold). Ce n'est pas un réglage esthétique :
    un IC de 0,04 produit des vues six fois plus faibles qu'un IC de 0,25, et le postérieur
    retombe alors sur le prior. C'est le mécanisme qui empêche une conviction non mesurée
    de déplacer un euro.

    Sans mesure, ou avec une mesure non robuste, le scénario N'EXISTE PAS. On ne le dégrade
    pas silencieusement en HRP sous un nom prometteur : on dit pourquoi il manque.
    """
    if not ic or not ic.get("available"):
        return None, ("IC du score jamais mesuré. Lancer `make ic-screening` : sans lui, "
                      "aucun rendement attendu n'est calibré et ce profil n'a pas de sens.")
    if not ic.get("robuste"):
        return None, (f"IC mesuré ({ic.get('ic_moyen', 0):+.4f}) mais NON robuste : "
                      f"{ic.get('ic_premiere_moitie', 0):+.4f} sur la première moitié contre "
                      f"{ic.get('ic_seconde_moitie', 0):+.4f} sur la seconde. Le signal ne "
                      "survit pas à sa période d'origine — on ne l'utilise pas.")
    try:
        from packages.portfolio.black_litterman import black_litterman, views_from_scores
        from packages.portfolio.optimize import equal_risk_contribution
        z, ic_total = vues_combinees(scores, ml_scores, float(ic["ic_moyen"]), somers_d(ml_auc))
        vol = float(np.sqrt(np.mean(np.diag(covariance))))       # vol annuelle typique
        matrice, vues = views_from_scores(list(z), scale=ic_total * vol)
        return black_litterman(covariance, equal_risk_contribution(covariance),
                               matrice, vues)["weights"], ""
    except Exception as erreur:  # noqa: BLE001
        return None, f"Black-Litterman indisponible : {erreur}"
