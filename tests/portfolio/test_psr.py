from packages.portfolio.psr import probabilistic_sharpe_ratio, deflated_sharpe_ratio


def test_psr_in_unit_interval_and_monotone():
    a = probabilistic_sharpe_ratio(0.1, 500)
    b = probabilistic_sharpe_ratio(0.2, 500)
    assert 0 <= a <= 1 and 0 <= b <= 1 and b > a    # plus de Sharpe → plus de confiance


def test_dsr_below_psr_due_to_multiple_testing():
    psr = probabilistic_sharpe_ratio(0.15, 500)
    dsr = deflated_sharpe_ratio(0.15, 500, n_trials=50)
    assert dsr <= psr                                # le seuil relevé réduit la proba


def test_short_sample():
    assert probabilistic_sharpe_ratio(0.2, 1) == 0.0
