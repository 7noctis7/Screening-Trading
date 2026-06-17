from packages.risk.limits import concentration_report


def test_breach_name():
    r = concentration_report({"A": 0.5, "B": 0.5}, max_name=0.20)
    assert not r["ok"] and any(b["type"] == "nom" for b in r["breaches"])


def test_hhi_and_effective_n():
    r = concentration_report({"A": 0.25, "B": 0.25, "C": 0.25, "D": 0.25})
    assert abs(r["hhi"] - 0.25) < 1e-9 and abs(r["effective_n"] - 4.0) < 0.1


def test_sector_breach():
    r = concentration_report({"A": 0.1}, {"Tech": 0.6}, max_sector=0.40)
    assert any(b["type"] == "secteur" for b in r["breaches"])
