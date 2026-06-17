from packages.execution.algos import twap_schedule, vwap_schedule, participation_cap


def test_twap_sums_to_total():
    s = twap_schedule(100, 4)
    assert len(s) == 4 and abs(sum(s) - 100) < 1e-6


def test_vwap_proportional():
    s = vwap_schedule(100, [1, 3])
    assert abs(sum(s) - 100) < 1e-6 and s[1] > s[0]


def test_vwap_empty_curve_falls_back():
    s = vwap_schedule(50, [])
    assert abs(sum(s) - 50) < 1e-6


def test_participation_cap():
    r = participation_cap(50, adv=1000, max_participation=0.1)
    assert r["within_cap"] and r["cap_qty"] == 100.0
    r2 = participation_cap(200, adv=1000, max_participation=0.1)
    assert not r2["within_cap"]
