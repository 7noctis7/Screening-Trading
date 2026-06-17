import numpy as np
from packages.ml.meta import meta_labels, evaluate


def test_meta_labels_correctness():
    proba = [0.8, 0.3, 0.9]
    y = [1, 0, 0]
    ml = meta_labels(proba, y)
    assert list(ml) == [1.0, 1.0, 0.0]   # 1er correct, 2e correct (0.3→0, y=0), 3e faux


def test_evaluate_meta_filters():
    rng = np.random.default_rng(0)
    y = (rng.random(200) < 0.5).astype(float)
    pp = np.clip(y * 0.6 + rng.random(200) * 0.4, 0, 1)
    mp = np.clip(y * 0.7 + rng.random(200) * 0.3, 0, 1)   # méta corrélé à la vérité
    r = evaluate(pp, mp, y)
    assert r["signals_meta"] <= r["signals_primary"]      # filtre → moins de signaux
    assert 0 <= r["precision_meta"] <= 1
