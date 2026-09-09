"""Minimiser la perte extrême, pas la dispersion.

Les optimiseurs de `optimize.py` raisonnent tous en variance. Or la variance traite une
journée à +8 % et une journée à −8 % exactement pareil, et personne ne se ruine sur des
hausses. Mesuré dans ce projet le 06/09 : min-variance pose 87 % (jusqu'à 99 % selon le
profil) sur l'actif le plus calme — ce n'est pas un bug, c'est sa définition.

« Le plus calme » et « celui qui perdra le moins le jour où tout tombe » sont deux
actifs différents dès que les pertes ne sont pas symétriques. Ces tests le mettent en
scène : un actif de faible variance mais à queue catastrophique, exactement le piège
qu'aucun optimiseur en variance ne peut voir.

Les scénarios sont SYNTHÉTIQUES et le restent : ils servent à valider la mathématique,
ce que le mandat données-réelles autorise explicitement dans tests/. Aucun seuil de
production n'est calibré ici.
"""

from __future__ import annotations

import numpy as np
import pytest

from packages.portfolio.cvar_optimize import (
    cvar_du_portefeuille,
    mean_cvar_detail,
    mean_cvar_weights,
    projeter_simplexe,
)
from packages.portfolio.optimize import min_variance_weights


def _piege_de_la_variance(t: int = 1200) -> np.ndarray:
    """Deux actifs : un « calme qui s'effondre », un « agité qui tient ».

    A — dérive douce, puis quelques krachs à −35 %. Faible variance, queue épouvantable.
    B — bruit ample et SYMÉTRIQUE, sans krach. Variance élevée, queue supportable.

    C'est la configuration où la variance et la perte extrême désignent des gagnants
    opposés. Sans elle, les deux optimiseurs tomberaient d'accord et le test ne
    prouverait rien.
    """
    g = np.random.default_rng(12345)
    a = g.normal(0.0004, 0.004, t)
    a[::150] = -0.35                      # un krach tous les 150 jours
    b = g.normal(0.0004, 0.020, t)        # trois fois plus agité, mais sans trou
    return np.column_stack([a, b])


# ------------------------------------------------------------------ projection

def test_la_projection_rend_un_portefeuille_investi() -> None:
    w = projeter_simplexe(np.array([0.7, -0.4, 2.0]))
    assert w.min() >= -1e-12, "poids négatif : le mandat est long-only"
    assert abs(w.sum() - 1.0) < 1e-9, "le portefeuille n'investit pas 100 %"


def test_le_plafond_par_ligne_est_respecte() -> None:
    w = projeter_simplexe(np.array([9.0, 0.1, 0.1, 0.1]), plafond=0.30)
    assert w.max() <= 0.30 + 1e-9, "le plafond par ligne a sauté"
    assert abs(w.sum() - 1.0) < 1e-9


def test_un_plafond_impossible_ne_rend_pas_un_portefeuille_incomplet() -> None:
    """Trois lignes plafonnées à 10 % ne peuvent pas totaliser 100 %. Rendre 30 %
    investi SANS le dire serait le pire des cas : on croirait être exposé."""
    w = projeter_simplexe(np.array([1.0, 1.0, 1.0]), plafond=0.10)
    assert abs(w.sum() - 1.0) < 1e-9


# ------------------------------------------------------------------------ CVaR

def test_le_cvar_est_bien_la_moyenne_des_pires_pertes() -> None:
    """Calcul vérifié à la main : 100 scénarios, les 5 pires valent −10 %."""
    r = np.zeros((100, 1))
    r[:5, 0] = -0.10
    assert cvar_du_portefeuille(r, [1.0], alpha=0.95) == pytest.approx(0.10)


def test_une_matrice_mal_formee_leve() -> None:
    with pytest.raises(ValueError):
        cvar_du_portefeuille(np.zeros((10, 3)), [1.0, 0.0])


# -------------------------------------------------- le test qui justifie le module

def test_mean_cvar_evite_le_piege_ou_min_variance_tombe() -> None:
    """LE test. Min-variance sur-pondère l'actif calme ; Mean-CVaR doit le fuir.

    Si les deux optimiseurs rendaient la même chose, ce module n'aurait aucune raison
    d'exister — d'où la vérification des DEUX côtés, pas seulement du nôtre.

    Mesuré ici : min-variance 33,5 % sur l'actif à krachs, Mean-CVaR 14,9 %. Une
    première version de ce test exigeait plus de 80 % pour min-variance, chiffre repris
    du cas à dix actifs du 06/09 ; à deux actifs il ne se reproduit pas. La prémisse
    était fausse, pas le code — corrigée plutôt qu'ajustée jusqu'à passer.
    """
    r = _piege_de_la_variance()
    w_var = min_variance_weights(np.cov(r, rowvar=False))
    w_cvar = mean_cvar_weights(r, alpha=0.95)

    assert w_var[0] > w_cvar[0] + 0.10, (
        f"min-variance pose {w_var[0]:.1%} sur l'actif à queue catastrophique et "
        f"Mean-CVaR {w_cvar[0]:.1%} : l'écart s'est refermé, donc soit le scénario ne "
        "piège plus la variance, soit l'optimiseur ne regarde plus la queue."
    )


def test_le_solveur_atteint_l_optimum_exact() -> None:
    """La formulation Rockafellar-Uryasev est un programme LINÉAIRE : on doit toucher
    l'optimum, pas s'en approcher. Comparé à un balayage fin sur 2 001 points."""
    r = _piege_de_la_variance()
    vrai = min(cvar_du_portefeuille(r, [x, 1 - x]) for x in np.linspace(0, 1, 2001))
    d = mean_cvar_detail(r)
    assert d["methode"].startswith("exact"), f"repli inattendu : {d['methode']}"
    assert d["cvar"] <= vrai + 1e-6, (
        f"CVaR obtenu {d['cvar']:.6f} contre {vrai:.6f} au balayage : le solveur "
        "n'atteint pas l'optimum du programme."
    )


def test_le_repli_sans_scipy_reste_utilisable() -> None:
    """Sans scipy, on tombe sur le sous-gradient projeté. Il doit rester MEILLEUR que
    l'équipondéré — sinon le repli serait pire que pas de repli du tout.

    Une première version calait son pas sur l'amplitude des rendements au lieu du
    diamètre du domaine : partie de 50 %, elle finissait à 44 % là où l'optimum était à
    15 %, donc pire que min-variance sur son propre objectif. Le code tournait et
    semblait converger. C'est cette comparaison-là qui l'a attrapé.
    """
    from packages.portfolio import cvar_optimize as mod

    r = _piege_de_la_variance()
    w = mod._resoudre_sousgradient(r, 0.95, 0.0, None, iters=800)
    n = r.shape[1]
    assert cvar_du_portefeuille(r, w) < cvar_du_portefeuille(r, [1.0 / n] * n), (
        "le repli fait moins bien que l'équipondéré : il ne sert à rien"
    )


def test_mean_cvar_reduit_reellement_la_perte_extreme() -> None:
    """Le seul critère qui compte : la perte des pires jours DIMINUE-T-ELLE ?

    Comparé à l'équipondéré ET à min-variance, sur les mêmes scénarios. Un optimiseur
    qui ne bat pas l'équipondéré sur son propre objectif ne sert à rien.
    """
    r = _piege_de_la_variance()
    n = r.shape[1]
    egal = [1.0 / n] * n
    w_var = min_variance_weights(np.cov(r, rowvar=False))
    w_cvar = mean_cvar_weights(r, alpha=0.95)

    c_egal = cvar_du_portefeuille(r, egal, 0.95)
    c_var = cvar_du_portefeuille(r, w_var, 0.95)
    c_cvar = cvar_du_portefeuille(r, w_cvar, 0.95)

    assert c_cvar < c_egal, f"pire que l'équipondéré : {c_cvar:.4f} ≥ {c_egal:.4f}"
    assert c_cvar < c_var, (
        f"pire que min-variance sur la queue : {c_cvar:.4f} ≥ {c_var:.4f}"
    )


def test_le_resultat_est_deterministe() -> None:
    """Deux appels identiques doivent rendre le même vecteur.

    Leçon du 07/09 : un banc dont deux exécutions diffèrent ne peut comparer ni deux
    versions du code, ni deux matériels — ce qui manquera précisément au moment de
    valider la migration GPU.
    """
    r = _piege_de_la_variance(400)
    assert mean_cvar_weights(r, iters=200) == mean_cvar_weights(r, iters=200)


def test_l_aversion_arbitre_entre_queue_et_rendement() -> None:
    """Le curseur qui engendre la frontière efficiente en Mean-CVaR : plus on demande de
    rendement, plus on accepte de queue. Sinon le paramètre serait décoratif."""
    g = np.random.default_rng(7)
    sur = g.normal(0.0002, 0.010, 900)          # peu rentable, peu risqué
    fort = g.normal(0.0030, 0.030, 900)         # rentable, plus risqué
    r = np.column_stack([sur, fort])

    prudent = mean_cvar_weights(r, aversion=0.0)
    gourmand = mean_cvar_weights(r, aversion=5.0)
    assert gourmand[1] > prudent[1], (
        "Demander du rendement ne déplace pas les poids : `aversion` ne sert à rien."
    )
    assert cvar_du_portefeuille(r, gourmand) >= cvar_du_portefeuille(r, prudent), (
        "Plus de rendement DOIT coûter de la queue — sinon le prudent est dominé, "
        "ce qui signalerait une erreur de signe."
    )


def test_le_plafond_tient_aussi_apres_optimisation() -> None:
    r = _piege_de_la_variance(500)
    w = mean_cvar_weights(r, plafond=0.55, iters=300)
    assert max(w) <= 0.55 + 1e-6
    assert abs(sum(w) - 1.0) < 1e-9


def test_un_seul_actif_donne_cent_pour_cent() -> None:
    assert mean_cvar_weights(np.array([[0.01], [-0.02], [0.005]])) == [1.0]


def test_des_scenarios_vides_levent_plutot_que_de_deviner() -> None:
    with pytest.raises(ValueError):
        mean_cvar_weights(np.zeros((1, 3)))
