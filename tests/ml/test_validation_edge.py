"""QML-011 — ce que l'onglet ML affiche doit tenir sur du bruit.

Trois défauts, mesurés le 25/09 :
  * la CV purgée recevait des indices POSITIONNELS par titre : purge et embargo ne portaient
    pas sur le temps calendaire dès que les séries ne démarraient pas le même jour ;
  * le Brier « calibré » était mesuré sur l'échantillon qui avait servi à ajuster Platt ;
  * `edge_ok = AUC ≥ 0,52` passait 5 fois sur 10 sur une marche aléatoire pure — et une borne
    basse calculée sur la dispersion des plis encore 4 fois sur 10 : les plis partagent le
    facteur de marché, leur dispersion sous-estime l'incertitude. Seule une distribution
    NULLE (permutation) peut établir un edge.
"""

from datetime import UTC, datetime, timedelta

import numpy as np

from packages.core.models import Bar


def test_bornes_du_label_en_jours_calendaires():
    from packages.ml.validation_edge import bornes_label
    d0 = datetime(2020, 1, 1, tzinfo=UTC)
    bars = [Bar("X", "1d", d0 + timedelta(days=3 * i), 1, 1, 1, 1, 1) for i in range(40)]
    t0, t1 = bornes_label(bars, 5, 21)
    assert t0 == (d0 + timedelta(days=15)).toordinal()
    assert t1 == (d0 + timedelta(days=78)).toordinal()


def test_deux_titres_meme_date_meme_borne_malgre_des_debuts_differents():
    from packages.ml.validation_edge import bornes_label
    d0 = datetime(2020, 1, 1, tzinfo=UTC)
    a = [Bar("A", "1d", d0 + timedelta(days=i), 1, 1, 1, 1, 1) for i in range(100)]
    b = a[30:]                                           # introduit 30 jours plus tard
    assert bornes_label(a, 50, 21) == bornes_label(b, 20, 21)


def test_sans_distribution_nulle_l_edge_n_est_jamais_affirme():
    from packages.ml.validation_edge import edge_detecte
    r = edge_detecte([0.60, 0.61, 0.59, 0.60, 0.62])
    assert r["edge"] is False and r["statut"] == "UNCALIBRATED"


def test_avec_distribution_nulle_l_edge_se_juge_par_p_valeur():
    from packages.ml.validation_edge import edge_detecte
    nulles = list(np.random.default_rng(0).normal(0.50, 0.015, 200))
    assert edge_detecte([0.60] * 5, auc_nulles=nulles)["edge"] is True
    assert edge_detecte([0.515] * 5, auc_nulles=nulles)["edge"] is False
    assert edge_detecte([0.60] * 5, auc_nulles=nulles[:10])["statut"] == "UNCALIBRATED"


def test_calibration_evaluee_hors_de_l_echantillon_d_ajustement():
    from packages.ml.validation_edge import calibration_hors_echantillon
    rng = np.random.default_rng(0)
    p = rng.uniform(0, 1, 400)
    y = (rng.uniform(0, 1, 400) < p).astype(float)
    r = calibration_hors_echantillon(p, y)
    assert r["available"] and r["n_ajustement"] == 200 and r["n_evaluation"] == 200
