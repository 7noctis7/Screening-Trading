"""Unicité : des labels chevauchants ne valent pas leur nombre de lignes."""
import numpy as np

from packages.ml.uniqueness import (average_uniqueness, concurrency,
                                    effective_sample_size, return_attribution_weights,
                                    time_decay_weights)


def test_concurrence_compte_les_labels_actifs():
    c = concurrency([0, 2, 4], [3, 5, 7], n_bars=8)
    assert list(c) == [1, 1, 2, 2, 2, 2, 1, 1]
    assert list(concurrency([0], [2], n_bars=4)) == [1, 1, 1, 0]


def test_labels_disjoints_sont_parfaitement_uniques():
    u = average_uniqueness([0, 3, 6], [2, 5, 8], n_bars=9)
    assert np.allclose(u, 1.0)
    assert effective_sample_size(u) == 3.0


def test_chevauchement_total_divise_l_unicite():
    u = average_uniqueness([0, 0, 0, 0], [9] * 4, n_bars=10)
    assert np.allclose(u, 0.25)                       # 4 copies de la même information
    assert effective_sample_size(u) == 1.0            # …valent UN échantillon


def test_taille_effective_bien_plus_petite_que_le_nombre_de_lignes():
    t0 = np.arange(0, 200)
    u = average_uniqueness(t0, t0 + 9, n_bars=210)    # labels à 10 barres, décalés de 1
    assert effective_sample_size(u) < 30              # 200 lignes ≈ 20 paris indépendants
    assert 0.05 < u.mean() < 0.2


def test_poids_par_attribution_de_rendement():
    r = np.zeros(30)
    r[5] = 0.05                                       # un seul mouvement, sur la barre 5
    w = return_attribution_weights([0, 10, 20], [9, 19, 29], r, n_bars=30)
    assert w[0] > w[1] and w[0] > w[2]                # le label qui capte le move pèse plus
    assert abs(w.mean() - 1.0) < 1e-9                 # normalisation à moyenne 1


def test_decroissance_temporelle():
    u = np.full(50, 0.5)
    w = time_decay_weights(u, last_weight=0.5)
    assert w[-1] > w[0] and abs(w[0] - 0.5) < 0.02    # le plus ancien pèse ~0,5
    plat = time_decay_weights(u, last_weight=1.0)
    assert np.allclose(plat, plat[0])                 # 1.0 = aucune décroissance
    coupe = time_decay_weights(u, last_weight=-0.5)
    assert coupe[0] == 0.0 and coupe[-1] > 0          # négatif = on écarte les plus vieux
