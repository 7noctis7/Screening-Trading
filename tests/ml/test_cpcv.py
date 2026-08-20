"""CPCV : plusieurs CHEMINS de backtest, et une purge qui tient réellement."""
import numpy as np
import pytest

from packages.ml.cpcv import CombinatorialPurgedCV, n_paths, path_assignments


def _labels(n=120, span=5):
    t0 = np.arange(n)
    return t0, t0 + span


def test_nombre_de_decoupages_et_de_chemins():
    assert n_paths(6, 2) == 5 and CombinatorialPurgedCV(6, 2).n_splits == 15
    assert n_paths(5, 1) == 1                      # k=1 → une seule séquence : le K-fold usuel
    assert n_paths(10, 2) == 9
    assert n_paths(3, 3) == 0                      # k doit rester < n


def test_purge_effective_aucun_chevauchement_train_test():
    t0, t1 = _labels()
    cv = CombinatorialPurgedCV(n_groups=6, k_test=2, embargo_pct=0.0)
    for train, test, _ in cv.split(t0, t1):
        assert not set(train) & set(test)
        for g0, g1 in zip(t0[test], t1[test]):
            assert not np.any((t1[train] >= g0) & (t0[train] <= g1))


def test_embargo_elargit_la_zone_purgee():
    t0, t1 = _labels()
    sans = CombinatorialPurgedCV(6, 2, embargo_pct=0.0)
    avec = CombinatorialPurgedCV(6, 2, embargo_pct=0.10)
    n_sans = [len(tr) for tr, _, _ in sans.split(t0, t1)]
    n_avec = [len(tr) for tr, _, _ in avec.split(t0, t1)]
    assert sum(n_avec) < sum(n_sans)


def test_chaque_groupe_est_teste_le_bon_nombre_de_fois():
    t0, t1 = _labels()
    cv = CombinatorialPurgedCV(6, 2)
    vus = {}
    for _, test, combo in cv.split(t0, t1):
        for g in combo:
            vus[g] = vus.get(g, 0) + 1
        assert len(test) > 0
    assert set(vus.values()) == {5}                # C(n-1, k-1) = C(5,1) = 5


def test_les_chemins_couvrent_tous_les_groupes_une_fois():
    chemins = path_assignments(6, 2)
    assert len(chemins) == 5
    for ch in chemins:
        assert sorted(g for g, _ in ch) == list(range(6))


def test_refuse_des_echantillons_non_tries():
    t0 = np.array([0, 5, 3, 9, 12, 20, 25, 30])
    with pytest.raises(ValueError, match="triés"):
        list(CombinatorialPurgedCV(4, 2).split(t0, t0 + 2))
