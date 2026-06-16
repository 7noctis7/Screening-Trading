from packages.alerts import Throttle


def test_dedup_within_ttl():
    t = {"now": 0.0}
    th = Throttle(ttl_s=100, clock=lambda: t["now"])
    assert th.allow("k") is True
    t["now"] = 50
    assert th.allow("k") is False        # même clé, fenêtre → bloqué
    t["now"] = 150
    assert th.allow("k") is True         # TTL écoulé → autorisé


def test_distinct_keys_independent():
    th = Throttle(ttl_s=100, clock=lambda: 0.0)
    assert th.allow("a") and th.allow("b")
