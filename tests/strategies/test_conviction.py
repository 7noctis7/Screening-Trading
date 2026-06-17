from packages.strategies.conviction import conviction_rank, conviction_weights


def test_rank_orders_by_blended_z():
    sig = {
        "A": {"trend": 0.3, "ml": 0.7, "fundamental": 0.8, "sentiment": 0.5},
        "B": {"trend": -0.2, "ml": 0.4, "fundamental": 0.3, "sentiment": -0.1},
        "C": {"trend": 0.1, "ml": 0.5, "fundamental": 0.5, "sentiment": 0.2},
    }
    r = conviction_rank(sig)
    assert r[0]["symbol"] == "A" and r[-1]["symbol"] == "B"
    assert all("conviction" in x and "components" in x for x in r)


def test_partial_components_ok():
    sig = {"A": {"trend": 0.5}, "B": {"ml": 0.9}, "C": {}}
    r = conviction_rank(sig)
    assert len(r) == 3                      # pas de crash si composantes manquantes


def test_weights_capped_and_normalized():
    ranked = [{"symbol": "A", "conviction": 3.0}, {"symbol": "B", "conviction": 1.0},
              {"symbol": "C", "conviction": 0.5}, {"symbol": "D", "conviction": -1.0}]
    w = conviction_weights(ranked, vol={"A": 0.2, "B": 0.2, "C": 0.2}, max_weight=0.5)
    assert abs(sum(w.values()) - 1.0) < 1e-6
    assert all(x <= 0.5 + 1e-9 for x in w.values())
    assert "D" not in w                     # conviction négative exclue
