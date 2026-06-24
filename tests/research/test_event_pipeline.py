"""Tests event-store PIT + feature store as-of + event-study (fondation alt-data)."""

import numpy as np

from packages.research.event_store import Event, append_events, load_events
from packages.research.event_study import car, significance
from packages.research.feature_store import asof_join, asof_price


# ── event-store ───────────────────────────────────────────────────────────
def test_event_hash_stable_and_dedup(tmp_path):
    p = tmp_path / "ev.jsonl"
    e1 = Event("2026-06-01T13:00:00Z", "insider_buy", ("AAPL",), "sec_edgar")
    e2 = Event("2026-06-01T13:00:00Z", "insider_buy", ("AAPL",), "sec_edgar")  # idem
    assert e1.hash == e2.hash
    assert append_events([e1], p) == 1
    assert append_events([e2], p) == 0          # dédup
    assert len(load_events(p)) == 1


def test_event_to_dict_has_ts_public():
    d = Event("2026-06-01T13:00:00Z", "8k", ("MSFT",), "sec").to_dict()
    assert d["ts_public"] == "2026-06-01T13:00:00Z" and "hash" in d


# ── feature store as-of (anti look-ahead) ───────────────────────────────────
def test_asof_price_takes_last_before_ts():
    ser = [("2026-06-01", 100.0), ("2026-06-02", 101.0), ("2026-06-03", 102.0)]
    assert asof_price(ser, "2026-06-02") == 101.0       # ≤ ts_public
    assert asof_price(ser, "2026-06-02T23:59:59Z") == 101.0
    assert asof_price(ser, "2026-05-31") is None         # event avant l'historique


def test_asof_join_never_uses_future_price():
    events = [{"hash": "h1", "ts_public": "2026-06-02", "type": "x",
               "tickers": ["AAPL"]}]
    prices = {"AAPL": [("2026-06-01", 100.0), ("2026-06-02", 101.0),
                       ("2026-06-03", 999.0)]}
    rows = asof_join(events, prices)
    assert rows[0]["asof_close"] == 101.0          # JAMAIS le 999 du futur


# ── event-study ─────────────────────────────────────────────────────────────
def test_car_sums_post_window():
    ret = [0.0, 0.0, 0.01, 0.02, 0.03, 0.0]
    assert abs(car(ret, event_idx=1, post=3) - 0.06) < 1e-9   # ret[2:5]


def test_event_study_detects_real_drift():
    # events suivis d'une dérive positive systématique → CAR>0, significatif vs placebo
    rng = np.random.default_rng(0)
    ret = rng.normal(0, 0.005, 600)
    events = list(range(20, 560, 25))
    for e in events:
        ret[e + 1: e + 6] += 0.02                  # +2%/j post-event
    out = significance(ret, events, post=5, n_sims=500, seed=1)
    assert out["available"] and out["mean_car"] > 0
    assert out["significant"] is True


def test_event_study_random_events_not_significant():
    rng = np.random.default_rng(2)
    ret = rng.normal(0, 0.01, 600)                         # pur bruit, aucun effet
    events = list(rng.integers(20, 560, size=20))
    out = significance(ret, events, post=5, n_sims=500, seed=3)
    assert out["available"] and out["significant"] is False
