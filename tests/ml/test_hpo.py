from packages.ml.hpo import optimize


def test_random_search_finds_optimum():
    # objectif maximal proche de x=0.7
    res = optimize(lambda p: -abs(p["x"] - 0.7), {"x": (0.0, 1.0)}, n_trials=60, seed=1)
    assert abs(res["best_params"]["x"] - 0.7) < 0.1
    assert res["engine"] in ("optuna", "random (repli)")
