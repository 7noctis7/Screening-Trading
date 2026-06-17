from packages.indicators.technical_score import technical_rating


def test_uptrend_high_score():
    closes = list(range(1, 260))           # tendance haussière nette
    r = technical_rating(closes)
    assert r["available"] and r["score"] >= 66 and r["label"] == "haussier"


def test_downtrend_low_score():
    closes = list(range(260, 1, -1))
    r = technical_rating(closes)
    assert r["score"] <= 40


def test_short_series_neutral():
    assert technical_rating([1, 2, 3])["available"] is False
