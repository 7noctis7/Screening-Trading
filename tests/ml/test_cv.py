import numpy as np
from packages.ml import PurgedKFold


def test_purges_overlapping_samples():
    n = 12
    t0 = np.arange(n)
    t1 = t0 + 3                       # labels chevauchants (3 barres)
    cv = PurgedKFold(n_splits=3, embargo_pct=0.0)
    for tr, te in cv.split(t0, t1):
        test_t0, test_t1 = t0[te].min(), t1[te].max()
        # aucun échantillon d'entraînement ne chevauche la fenêtre de test
        assert not ((t1[tr] >= test_t0) & (t0[tr] <= test_t1)).any()
        assert not set(tr) & set(te)


def test_embargo_widens_purge():
    n = 20
    t0 = np.arange(n); t1 = t0 + 1
    no_emb = sum(len(tr) for tr, _ in PurgedKFold(4, 0.0).split(t0, t1))
    emb = sum(len(tr) for tr, _ in PurgedKFold(4, 0.2).split(t0, t1))
    assert emb <= no_emb              # l'embargo retire au moins autant
