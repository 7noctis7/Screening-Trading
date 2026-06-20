import pytest

np = pytest.importorskip("numpy")               # cœur ML : sauté si numpy absent (sandbox sans deps)
from packages.ml import (LogitModel, make_model, accuracy, precision_recall,
                         champion_challenger, ModelRegistry)


def _separable(n=200, seed=0):
    rng = np.random.default_rng(seed)
    X = rng.normal(0, 1, (n, 3))
    y = (X[:, 0] + 0.3 * rng.normal(0, 1, n) > 0).astype(int)
    return X, y


def test_logit_learns_separable():
    X, y = _separable()
    m = LogitModel().fit(X, y)
    assert accuracy(y, m.predict(X)) > 0.85


def test_logit_handles_nan():
    X, y = _separable()
    X[0, 0] = np.nan
    m = LogitModel().fit(X, y)
    assert m.predict(X).shape == y.shape   # pas de crash


def test_sklearn_adapter_runs():
    pytest.importorskip("sklearn")              # adaptateur scikit-learn optionnel
    X, y = _separable()
    m = make_model("sklearn").fit(X, y)
    assert accuracy(y, m.predict(X)) > 0.8


def test_precision_recall():
    p, r = precision_recall(np.array([1, 1, 0, 0]), np.array([1, 0, 0, 0]))
    assert p == 1.0 and r == 0.5


def test_champion_challenger_rules():
    assert champion_challenger(0.6, None).promote                       # initial
    assert champion_challenger(0.65, 0.60, min_improvement=0.02).promote
    assert not champion_challenger(0.61, 0.60, min_improvement=0.02).promote
    assert not champion_challenger(0.9, 0.6, risk_ok=False).promote     # risque bloque


def test_registry_promotes_best():
    reg = ModelRegistry()
    reg.consider("a", None, 0.55)
    reg.consider("b", None, 0.60)
    assert reg.champion == "b"
    reg.consider("c", None, 0.605)        # +0.005 < seuil → pas promu
    assert reg.champion == "b"
