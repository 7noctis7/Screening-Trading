"""Orthogonalisation : ce qui reste après avoir retiré les bêtas est le seul alpha."""
import numpy as np

from packages.ranking.orthogonalize import (combine_signals, factor_exposure, group_z,
                                            neutralize, qr_orthogonalize, robust_z)


def test_z_robuste_resiste_a_un_outlier():
    base = list(np.linspace(-1, 1, 50))
    classique = lambda v: (np.array(v) - np.mean(v)) / np.std(v, ddof=1)   # noqa: E731
    avec = base + [500.0]
    deplacement = abs(np.median(classique(avec)))
    assert deplacement > 0.1                             # la moyenne est déplacée
    z = robust_z(avec)
    assert abs(np.median(z[:-1])) < deplacement / 4      # la médiane tient bien mieux
    assert z[-1] == 3.0                                  # outlier écrêté, pas propagé
    assert np.all(np.isfinite(robust_z([1.0, np.nan, 2.0])))


def test_groupes_trop_petits_replient_sur_le_global():
    vals = np.arange(24, dtype=float)
    groupes = np.array(["A"] * 12 + ["B"] * 10 + ["C"] * 2)
    z = group_z(vals, groupes, min_size=10)
    assert abs(np.median(z[groupes == "A"])) < 1e-9      # A démoyenné : médiane nulle
    assert abs(np.median(z[groupes == "B"])) < 1e-9
    assert np.median(z[groupes == "C"]) > 1.0            # C non démoyenné (trop petit)


def test_qr_produit_des_colonnes_orthogonales_et_l_ordre_compte():
    rng = np.random.default_rng(0)
    a = rng.normal(size=200)
    b = 0.9 * a + 0.4 * rng.normal(size=200)             # signaux très corrélés
    S = np.column_stack([a, b])
    Q = qr_orthogonalize(S)
    assert abs(np.corrcoef(Q[:, 0], Q[:, 1])[0, 1]) < 1e-9
    assert abs(float(Q[:, 0] @ Q[:, 1])) < 1e-9
    assert abs(np.corrcoef(Q[:, 0], a)[0, 1]) > 0.99     # la 1re colonne garde tout le partagé
    Q2 = qr_orthogonalize(np.column_stack([b, a]))
    assert abs(np.corrcoef(Q2[:, 0], b)[0, 1]) > 0.99    # ordre inversé → résultat différent


def test_neutralisation_annule_les_expositions_factorielles():
    rng = np.random.default_rng(1)
    n = 300
    beta = rng.normal(1.0, 0.3, n)
    taille = rng.normal(size=n)
    B = np.column_stack([beta, taille])
    alpha = 2.0 * beta - 1.5 * taille + 0.3 * rng.normal(size=n)   # 90 % de bêta déguisé
    assert np.max(np.abs(factor_exposure(alpha, B))) > 100
    resid = neutralize(alpha, B)
    assert np.max(np.abs(factor_exposure(resid, B))) < 1e-6
    assert np.std(resid) < 0.4 * np.std(alpha)           # l'alpha « pur » est bien plus petit


def test_neutralisation_ponderee_et_robustesse():
    rng = np.random.default_rng(2)
    B = rng.normal(size=(100, 3))
    a = rng.normal(size=100)
    w = np.abs(rng.normal(1.0, 0.2, 100))
    assert np.max(np.abs(factor_exposure(neutralize(a, B, w), B, w))) < 1e-6
    assert np.allclose(neutralize(a, np.zeros((100, 0))), a)       # aucun facteur → inchangé


def test_combinaison_optimale_penalise_la_redondance():
    rng = np.random.default_rng(3)
    x = rng.normal(size=(500, 1))
    Z_redondant = np.hstack([x, x + 0.05 * rng.normal(size=(500, 1))])
    Z_independant = rng.normal(size=(500, 2))
    ic = np.array([0.04, 0.04])
    red = combine_signals(Z_redondant, ic, shrink=0.05)
    ind = combine_signals(Z_independant, ic, shrink=0.05)
    assert ind["ic_combined"] > red["ic_combined"]        # deux vrais signaux valent plus
    assert abs(ind["ic_combined"] - ind["ic_naive_sum"]) < 0.01
    assert red["ic_combined"] < red["ic_naive_sum"]       # la somme quadratique surestime
    assert abs(np.abs(red["weights"]).sum() - 1.0) < 1e-9
