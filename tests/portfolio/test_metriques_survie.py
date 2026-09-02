"""Ulcer, temps sous l'eau, linéarité, ES de Cornish-Fisher — valeurs EXACTES.

Ces quatre mesures servent à décider si une stratégie est vivable. Chacune est donc
vérifiée contre un nombre calculé à la main, pas contre elle-même.
"""

import math

from packages.portfolio.metriques_survie import (
    _z_normal,
    r2_linearite,
    temps_sous_l_eau,
    ulcer_index,
    var_es_cornish_fisher,
)


def _croissante(n: int = 300, taux: float = 0.0005) -> list[float]:
    return [100.0 * (1 + taux) ** i for i in range(n)]


def _asymetrique(c: float, n: int = 1000, sd: float = 0.01) -> list[float]:
    """Échantillon DÉTERMINISTE d'asymétrie réglable : quantiles normaux déformés.

    Déterministe et non tiré au hasard : un test de queue dont le verdict dépend d'une
    graine se met à clignoter, et un test qui clignote finit par être ignoré.
    `c < 0` incline vers la gauche, `c > 0` vers la droite.
    """
    return [sd * (z + c * (z * z - 1)) + 0.0005
            for z in (_z_normal((i + 0.5) / n) for i in range(n))]


def test_ulcer_nul_sur_une_courbe_qui_ne_recule_jamais():
    """Aucun drawdown, donc aucun stress — l'indice doit valoir exactement 0."""
    assert ulcer_index(_croissante())["ulcer"] == 0.0


def test_ulcer_en_points_de_pourcentage_et_non_en_fraction():
    """La cible « UI <= 4,5 » de la spec n'a de sens que dans cette unité."""
    eq = [100.0] * 30
    eq[10] = 90.0                                  # un seul point à -10 %
    r = ulcer_index(eq)
    # tolérance = l'arrondi d'affichage du module (3 décimales), pas une marge de confort
    assert abs(r["ulcer"] - math.sqrt(100.0 / 30.0)) < 5e-4
    assert 1.8 < r["ulcer"] < 1.9                  # ~1,83 point de %, pas 0,018


def test_ulcer_penalise_la_profondeur_au_carre():
    """Deux fois plus profond doit compter QUATRE fois, pas deux."""
    peu, beaucoup = [100.0] * 40, [100.0] * 40
    peu[10], beaucoup[10] = 95.0, 90.0
    a = ulcer_index(peu)["ulcer"]
    b = ulcer_index(beaucoup)["ulcer"]
    assert abs(b / a - 2.0) < 2e-3                 # racine de 4 = 2 sur un seul point


def test_temps_sous_l_eau_compte_strictement_sous_le_sommet():
    eq = [100.0] * 40
    for k in range(10, 20):
        eq[k] = 95.0
    r = temps_sous_l_eau(eq)
    assert r["part_sous_l_eau"] == 0.25            # 10 points sur 40
    assert r["plus_longue_serie"] == 10
    assert temps_sous_l_eau(_croissante())["part_sous_l_eau"] == 0.0


def test_r2_vaut_un_sur_une_croissance_a_taux_constant():
    """LE point où la spec se trompe : une equity composée n'est pas une droite.

    Régresser le NIVEAU d'une croissance parfaitement régulière donnerait un R² dégradé
    et ferait rejeter la stratégie la plus régulière qui soit. On régresse le log.
    """
    r = r2_linearite(_croissante())
    assert r["available"] and abs(r["r2"] - 1.0) < 1e-9
    assert r["echelle"] == "log"


def test_r2_s_effondre_quand_la_performance_tient_a_une_seule_barre():
    """C'est l'usage légitime du critère : détecter le trade aberrant unique."""
    eq = [100.0] * 150 + [200.0] * 150
    assert r2_linearite(eq)["r2"] < 0.80


def test_cornish_fisher_aggrave_la_queue_d_une_distribution_asymetrique():
    """Une queue gauche épaisse doit donner un ES PIRE que la version gaussienne.

    Ce test a fait tomber une VRAIE erreur (02/09) : la première version n'évaluait que
    la densité normale au quantile corrigé, sans le crochet de Boudt-Peterson-Croux.
    L'ES ressortait alors PLUS CLÉMENT que le gaussien alors que la VaR, elle, était bien
    aggravée — une mesure de queue rassurante sur une distribution qui ne l'est pas.
    """
    d = var_es_cornish_fisher(_asymetrique(-0.15), alpha=0.99)
    assert d["available"] and d["valide"]
    assert d["skew"] < -0.5
    assert d["es_modifie"] < d["es_gaussien"]      # plus négatif = perte plus lourde
    assert d["es_modifie"] < d["var_modifiee"]     # une moyenne de queue passe le quantile


def test_cornish_fisher_refuse_d_alleger_la_queue_et_replie_sur_l_historique():
    """LE mode de panne à éviter : une correction qui RASSURE sur une mesure de queue.

    Hors du domaine d'admissibilité, l'expansion cesse d'être un quantile valide et peut
    rendre la perte moins sévère. On préfère le dire et se replier plutôt que publier un
    chiffre confortable et faux.
    """
    d = var_es_cornish_fisher(_asymetrique(+0.60), alpha=0.99)
    assert d["available"] and d["skew"] > 1.0
    assert d["valide"] is False
    assert d["es_modifie"] == d["es_historique"]
    assert "repli historique" in d["motif"]


def test_cornish_fisher_sort_du_domaine_sur_une_queue_extreme():
    """L'expansion diverge bien avant qu'on le remarque : ici, un ES six fois pire que
    la pire perte observée. Le garde-fou doit l'attraper, pas le publier."""
    d = var_es_cornish_fisher([0.004] * 950 + [-0.09] * 50, alpha=0.99)
    assert d["skew"] < -4.0 and d["kurtosis_excedentaire"] > 10.0
    assert d["valide"] is False
    assert "hors domaine" in d["motif"]
    assert d["es_modifie"] == -0.09                # repli : la moyenne du pire centile


def test_pas_de_chiffre_publie_sur_un_echantillon_trop_court():
    """Une mesure de queue à 99 % sur 50 points ne mesure rien : on refuse de la rendre."""
    assert var_es_cornish_fisher([0.01, -0.01] * 25)["available"] is False
    assert ulcer_index([100.0] * 10)["available"] is False
