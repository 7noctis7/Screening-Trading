"""Ratios d'une allocation — tous MESURÉS sur l'historique, aucun n'est une prévision.

La distinction gouverne ce module. Un ratio de diversification, une distance au plus haut,
une volatilité réalisée sont des CONSTATS : ils décrivent ce qui s'est produit ou ce que la
matrice de covariance implique aujourd'hui. Un objectif de cours est une PRÉVISION : il
n'appartient pas ici, et la journée du 07/09 a montré pourquoi — l'IC du score de sélection
mesuré à +0,02 (t = 0,76) dit qu'aucune anticipation n'est démontrée dans ce dépôt.

Le Sharpe réalisé est le cas limite : c'est un constat, mais il se lit spontanément comme
une promesse. Il est donc rendu sous une clé explicitement rétrospective, à charge de
l'affichage de ne jamais le présenter comme attendu.
"""
from __future__ import annotations

import numpy as np

JOURS_52_SEMAINES = 252


def bornes_52_semaines(serie: dict[str, float], jours: int = JOURS_52_SEMAINES) -> dict:
    """Plus haut, plus bas, dernier cours, et distance au plus haut sur la fenêtre.

    La distance au plus haut est le seul des quatre qui se lise sans contexte : −40 % dit
    qu'il faut +67 % pour revenir, une asymétrie que le pourcentage de baisse masque.
    """
    if not serie:
        return {"haut_52s": None, "bas_52s": None, "dernier": None, "distance_haut": None}
    dates = sorted(serie)[-jours:]
    valeurs = [float(serie[d]) for d in dates if serie[d]]
    if not valeurs:
        return {"haut_52s": None, "bas_52s": None, "dernier": None, "distance_haut": None}
    haut, bas, dernier = max(valeurs), min(valeurs), valeurs[-1]
    return {"haut_52s": haut, "bas_52s": bas, "dernier": dernier,
            "distance_haut": (dernier / haut - 1.0) if haut > 0 else None,
            "position_dans_bande": ((dernier - bas) / (haut - bas)) if haut > bas else None}


def _vols(covariance: np.ndarray) -> np.ndarray:
    return np.sqrt(np.maximum(0.0, np.diag(np.asarray(covariance, dtype=float))))


def ratio_diversification(poids, covariance) -> float | None:
    """(Σ wᵢσᵢ) / σ_portefeuille — combien la corrélation fait GAGNER, en un nombre.

    Vaut 1,0 quand tout est parfaitement corrélé : détenir dix lignes n'apporte alors rien
    de plus qu'une seule. Au-delà de 2, la diversification travaille vraiment. C'est le
    complément indispensable au nombre de lignes, qui ne dit rien de leur redondance.
    """
    w = np.asarray(poids, dtype=float)
    somme = float(w @ _vols(covariance))
    variance = float(w @ np.asarray(covariance, dtype=float) @ w)
    if variance <= 0 or somme <= 0:
        return None
    return somme / float(np.sqrt(variance))


def positions_effectives(poids) -> float | None:
    """1/Σw² — le nombre de lignes ÉQUIPONDÉRÉES qui aurait la même concentration.

    Quatorze lignes dont une à 38 % ne valent pas quatorze lignes : ce nombre le dit.
    """
    w = np.asarray(poids, dtype=float)
    carre = float(w @ w)
    return (1.0 / carre) if carre > 0 else None


def correlation_moyenne(covariance) -> float | None:
    """Corrélation moyenne des paires — la matière première de la diversification."""
    cov = np.asarray(covariance, dtype=float)
    sigma = _vols(cov)
    if cov.shape[0] < 2 or not np.all(sigma > 0):
        return None
    corr = cov / np.outer(sigma, sigma)
    haut = corr[np.triu_indices_from(corr, k=1)]
    return float(np.mean(haut)) if haut.size else None


def performance_realisee(series: dict[str, dict[str, float]], symboles: list[str],
                         poids) -> dict:
    """Ce que cette allocation AURAIT fait sur la fenêtre commune — rétrospectif.

    Ce n'est pas un rendement attendu, et l'écart n'est pas rhétorique : l'allocation a été
    choisie EN CONNAISSANT ces prix. Le chiffre est donc biaisé vers le haut par
    construction, et sa seule lecture honnête est comparative — entre les profils, sur la
    même fenêtre, pas comme une projection.
    """
    dates = sorted(set.intersection(*(set(series[s]) for s in symboles))) if symboles else []
    if len(dates) < 30:
        return {"rendement_annualise": None, "sharpe_realise": None, "n_observations": len(dates)}
    prix = np.asarray([[series[s][d] for d in dates] for s in symboles], dtype=float)
    rendements = prix[:, 1:] / prix[:, :-1] - 1.0
    portefeuille = np.asarray(poids, dtype=float) @ rendements
    moyenne, ecart = float(portefeuille.mean()), float(portefeuille.std(ddof=1))
    return {"rendement_annualise": moyenne * 252,
            "sharpe_realise": (moyenne / ecart * np.sqrt(252)) if ecart > 0 else None,
            "n_observations": int(portefeuille.size),
            "avertissement": "rétrospectif — l'allocation connaissait ces prix"}
