"""La règle « ATR > 200 % de sa moyenne 30 » vérifiée sur des barres CONSTRUITES.

Synthétique assumé : on valide ici la MATH (pas de regard en avant, fenêtres pleines,
verdicts qui refusent de conclure). La mesure sur données réelles est le travail de
`scripts/regime_atr_lab.py`, qui n'a sa place ni dans un test ni en CI.
"""

from __future__ import annotations

from packages.research import regime_atr as R


def _barres(ranges: list[float], depart: float = 100.0):
    """Des barres dont le true range vaut exactement `ranges[i]`, clôture constante.

    Clôture plate : le TR se réduit à haut − bas, donc le ratio ATR/moyenne est
    entièrement pilotable — ce qui permet de poser un seuil et de savoir ce qui
    doit le franchir.
    """
    hauts, bas, clotures = [], [], []
    for r in ranges:
        hauts.append(depart + r / 2)
        bas.append(depart - r / 2)
        clotures.append(depart)
    return hauts, bas, clotures


def test_la_premiere_barre_n_a_pas_de_true_range():
    h, b, c = _barres([1.0, 1.0, 1.0])
    assert R.true_range(h, b, c)[0] is None


def test_le_ratio_reste_inconnu_tant_que_les_fenetres_ne_sont_pas_pleines():
    """Barre 0 sans TR, puis 14 TR pour l'ATR, puis 30 ATR pour la moyenne : 43 barres.

    Le compte exact importe : une fenêtre remplie une barre trop tôt moyennerait
    l'ATR sur moins de points que ce qui est annoncé, et le ratio serait plus
    nerveux que ce que la spec décrit.
    """
    h, b, c = _barres([1.0] * 60)
    r = R.ratios(h, b, c)
    assert all(x is None for x in r[:43])
    assert r[43] is not None


def test_une_volatilite_constante_donne_un_ratio_de_un():
    h, b, c = _barres([2.0] * 80)
    r = [x for x in R.ratios(h, b, c) if x is not None]
    assert r and all(abs(x - 1.0) < 1e-9 for x in r)


def test_une_explosion_de_volatilite_franchit_le_seuil():
    h, b, c = _barres([1.0] * 80 + [40.0] * 20)
    assert max(x for x in R.ratios(h, b, c) if x is not None) > R.SEUIL_SPEC


def test_aucune_barre_n_est_classee_sans_son_rendement_futur():
    """L'horizon ampute la fin : classer la dernière barre inventerait son futur."""
    h, b, c = _barres([1.0] * 60)
    d = R.classer(h, b, c, horizon=5, chevauchement=True)
    connus = len([x for x in R.ratios(h, b, c) if x is not None])
    assert len(d["haute"]) + len(d["basse"]) == connus - 5


def test_les_fenetres_ne_se_chevauchent_pas_par_defaut():
    """Cinq barres voisines partagent quatre jours sur cinq : les compter cinq fois
    gonfle n, rétrécit l'erreur-type, et fabrique une séparation entre régimes."""
    h, b, c = _barres([1.0] * 120)
    sans = R.classer(h, b, c, horizon=5)
    avec = R.classer(h, b, c, horizon=5, chevauchement=True)
    n_sans = len(sans["haute"]) + len(sans["basse"])
    n_avec = len(avec["haute"]) + len(avec["basse"])
    assert n_avec > 4 * n_sans       # facteur évité, de l'ordre de l'horizon


def test_le_rendement_classe_est_bien_posterieur():
    """Le saut est placé sur la DERNIÈRE barre, qui n'est elle-même jamais classée.

    C'est ce qui rend le test discriminant. À horizon 1, seule l'avant-dernière barre
    peut voir ce saut, et elle ne le voit qu'en regardant DEVANT elle. Une version
    qui mesurerait le rendement passé attribuerait le saut à la dernière barre —
    hors classement — et le +10 % n'apparaîtrait nulle part.
    """
    h, b, c = _barres([1.0] * 60)
    c[-1] = 110.0
    d = R.classer(h, b, c, horizon=1)
    sauts = [x for x in d["basse"] + d["haute"] if abs(x - 0.10) < 1e-9]
    assert len(sauts) == 1


def test_une_regle_qui_ne_mord_jamais_est_dite_inerte():
    v = R.verdict([], [0.01] * 600)
    assert v["statut"] == "REGLE_INERTE"
    assert "jamais" in v["message"]


def test_trop_peu_d_observations_ne_donne_pas_de_verdict():
    v = R.verdict([0.02] * 5, [0.01] * 600)
    assert v["statut"] == "UNCALIBRATED"


def test_sous_le_plancher_d_entrainement_le_modele_dedie_est_impossible():
    """Le t peut être énorme : 400 lignes ne font pas un modèle entraînable."""
    v = R.verdict([0.05] * 400, [0.0] * 600)
    assert v["statut"] == "NON_ENTRAINABLE"
    assert v["entrainable_haute"] is False
    assert v["entrainable_basse"] is True


def test_sans_dates_le_verdict_refuse_de_dire_MESURE():
    """Le t brut est une borne haute. Il ne doit pas se faire passer pour une mesure."""
    v = R.verdict([0.05, -0.05] * 300, [0.01, -0.01] * 300)
    assert v["statut"] == "MESURE_NON_GROUPEE"
    assert "borne haute" in v["message"]
    assert v["welch"]["disponible"] is True


def _datees(valeurs, n_jours):
    """Répartit `valeurs` sur `n_jours` journées distinctes, en tournant."""
    return [(f"2020-01-{1 + i % n_jours:02d}", x) for i, x in enumerate(valeurs)]


def test_mille_lignes_sur_trois_journees_ne_font_pas_mille_tirages():
    """Le cas qui compte : un pic de volatilité traversé par tout l'univers.

    Mille observations brutes, trois épisodes. Le t brut « prouve » une séparation ;
    le regroupement rend les trois journées visibles et le verdict refuse de conclure.
    """
    haute, basse = [0.05, -0.03] * 500, [0.01, -0.01] * 500
    v = R.verdict(haute, basse, haute_datees=_datees(haute, 3),
                  basse_datees=_datees(basse, 400))
    assert v["statut"] == "UNCALIBRATED"
    assert v["n_jours_haute"] == 3
    assert v["welch"]["disponible"] is True        # le t brut existe bien…
    assert "pas autant d'épisodes distincts" in v["message"]   # …et ne décide pas


def test_assez_de_journees_distinctes_rend_une_mesure():
    haute, basse = [0.05, -0.03] * 300, [0.01, -0.01] * 300
    v = R.verdict(haute, basse, haute_datees=_datees(haute, 31),
                  basse_datees=_datees(basse, 31))
    assert v["statut"] == "MESURE"
    assert v["welch_groupe"]["disponible"] is True
    assert v["n_jours_haute"] == 31


def test_le_regroupement_par_date_moyenne_dans_la_journee():
    obs = [("2020-01-01", 0.10), ("2020-01-01", 0.20), ("2020-01-02", 0.30)]
    assert R.moyennes_par_date(obs) == [0.15000000000000002, 0.3]


def test_un_horodatage_se_reduit_a_sa_journee_quelle_que_soit_sa_forme():
    from datetime import datetime
    assert R.jour(datetime(2020, 3, 16, 20, 0)) == "2020-03-16"
    assert R.jour("2020-03-16T20:00:00Z") == "2020-03-16"


def test_welch_refuse_une_variance_nulle_des_deux_cotes():
    """Deux constantes exactes : aucun écart-type, donc aucun t à calculer."""
    assert R.welch([1.0] * 10, [2.0] * 10)["disponible"] is False


def test_welch_ne_separe_pas_deux_echantillons_identiques():
    w = R.welch([0.01, 0.02] * 50, [0.01, 0.02] * 50)
    assert w["disponible"] and abs(w["t"]) < 1e-6


def test_welch_separe_deux_moyennes_franchement_differentes():
    w = R.welch([0.10, 0.11] * 300, [-0.10, -0.11] * 300)
    assert w["disponible"] and w["t"] > 10 and w["ecart_moyen"] > 0.19
