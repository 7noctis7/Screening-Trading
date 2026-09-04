"""UNE définition de la déviation baissière — les deux erreurs classiques la gonflent.

Le dépôt calculait Sortino de trois façons et publiait les trois côte à côte. Deux
ratios calculés autrement ne se comparent pas : un Sortino de la page A et un Sortino
de la page B décrivaient le même portefeuille avec des chiffres différents, sans que
rien ne l'indique.
"""

from __future__ import annotations

import statistics as st

from packages.portfolio.deviation import deviation_baissiere, sortino_annualise


def test_la_definition_divise_par_N_TOTAL_pas_par_le_nombre_de_pertes():
    """Le cœur du sujet : Sortino doit dépendre de la FRÉQUENCE des pertes. Diviser par
    le nombre de négatifs efface exactement cette dépendance."""
    r = [0.0] * 9 + [-0.10]
    assert abs(deviation_baissiere(r) - (0.01 / 10) ** 0.5) < 1e-12
    # une seule perte identique, mais diluée dans dix fois plus de séances calmes
    r2 = [0.0] * 99 + [-0.10]
    assert deviation_baissiere(r2) < deviation_baissiere(r)


def test_les_gains_ne_comptent_pas_dans_la_deviation_BAISSIERE():
    """Seuls les rendements sous le seuil entrent ; un gain n'est pas un risque."""
    assert deviation_baissiere([0.05, 0.10, 0.02]) == 0.0
    assert deviation_baissiere([0.05, -0.02]) == deviation_baissiere([0.90, -0.02])


def test_les_deux_conventions_fautives_GONFLENT_le_ratio():
    """Mesure du 04/09, reproduite ici : 2 520 rendements pseudo-aléatoires. Les deux
    erreurs vont dans le même sens — un Sortino plus flatteur que la définition."""
    import random
    random.seed(7)
    r = [random.gauss(0.0005, 0.012) for _ in range(2520)]
    juste = deviation_baissiere(r)
    ecart_negatifs = st.stdev([x for x in r if x < 0])
    ecart_clip = st.stdev([min(0.0, x) for x in r])
    assert ecart_negatifs < juste and ecart_clip < juste     # donc Sortino plus élevé
    assert 1.10 < juste / ecart_negatifs < 1.16              # ≈ ×1,128
    assert 1.16 < juste / ecart_clip < 1.22                  # ≈ ×1,191


def test_un_seuil_non_nul_deplace_la_reference():
    """Sortino accepte un seuil (MAR). Avec 0,01, un rendement de 0,005 devient une
    perte relative — c'est le sens du paramètre."""
    assert deviation_baissiere([0.005], seuil=0.0) == 0.0
    assert abs(deviation_baissiere([0.005], seuil=0.01) - 0.005) < 1e-12


def test_les_cas_degeneres_ne_levent_pas():
    assert deviation_baissiere([]) == 0.0
    assert sortino_annualise([]) == 0.0
    assert sortino_annualise([0.01]) == 0.0          # un point : aucun ratio
    assert sortino_annualise([0.01, 0.02]) == 0.0    # aucune perte : non défini


def test_le_taux_sans_risque_est_ANNUEL_comme_pour_sharpe():
    """Un rf traité comme périodique diviserait le ratio par ~252 sans rien signaler."""
    r = [0.001] * 200 + [-0.01] * 52
    sans = sortino_annualise(r, rf=0.0)
    avec = sortino_annualise(r, rf=0.02)
    assert avec < sans
    assert abs(sans - avec) < abs(sans)              # effet modeste, pas un facteur 252


def test_les_quatre_appelants_partagent_la_definition():
    """Le point de la refonte : la même série doit produire le MÊME Sortino partout."""
    from packages.portfolio.metrics import perf_summary, sortino
    eq, v = [100.0], 100.0
    for i in range(300):
        v *= 1 + (0.002 if i % 3 else -0.004)
        eq.append(v)
    direct = sortino(eq)
    resume = perf_summary(eq)["sortino"]
    assert abs(direct - resume) < 1e-9 or abs(round(direct, 3) - resume) < 1e-9
