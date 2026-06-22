from packages.ml.promotion import ModelMetrics, should_promote


def test_first_model_adopted_if_viable():
    ok, _ = should_promote(ModelMetrics(dsr=0.5, brier=0.18), None)
    assert ok


def test_first_model_rejected_if_no_edge_or_miscalibrated():
    assert not should_promote(ModelMetrics(dsr=-0.1, brier=0.18), None)[0]
    assert not should_promote(ModelMetrics(dsr=0.5, brier=0.30), None)[0]


def test_challenger_must_beat_champion_dsr():
    champ = ModelMetrics(dsr=0.6, brier=0.20)
    assert not should_promote(ModelMetrics(dsr=0.55, brier=0.18), champ)[0]   # DSR pire
    assert should_promote(ModelMetrics(dsr=0.7, brier=0.20), champ)[0]        # DSR meilleur


def test_challenger_rejected_on_calibration_regression():
    champ = ModelMetrics(dsr=0.6, brier=0.18)
    # meilleur DSR mais calibration nettement pire → refus
    assert not should_promote(ModelMetrics(dsr=0.8, brier=0.23), champ)[0]
