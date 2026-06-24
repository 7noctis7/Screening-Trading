"""Tests du moteur de screening (filtres YAML + scoring z-score)."""

from datetime import UTC, datetime, timedelta

import pytest

from packages.core.models import Bar
from packages.screening import ScreeningEngine, available_metrics
from tests._helpers import mkbars


def _rule(metric, op, value, **kw):
    return {"metric": metric, "op": op, "value": value, **kw}


def _bars_vol(prices, vol, symbol="X"):
    """Barres à volume contrôlé (test liquidité) ; mkbars fixe volume=1000."""
    t0 = datetime(2024, 1, 1, tzinfo=UTC)
    return [Bar(symbol, "1d", t0 + timedelta(days=i), p, p * 1.01, p * 0.99, p, vol)
            for i, p in enumerate(prices)]


def _up(n=300, lo=50.0, hi=200.0):
    step = (hi - lo) / (n - 1)
    return [lo + step * i for i in range(n)]


def _down(n=300, hi=200.0, lo=50.0):
    step = (hi - lo) / (n - 1)
    return [hi - step * i for i in range(n)]


def test_filter_keeps_uptrend_rejects_downtrend_and_missing():
    panel = {
        "UP": mkbars(_up(), "UP"),
        "DOWN": mkbars(_down(), "DOWN"),
        "SHORT": mkbars([100.0] * 50, "SHORT"),  # < 200 barres → above_sma200 = NaN
    }
    eng = ScreeningEngine({"filters": [_rule("above_sma200", ">=", 1)]})
    res = eng.screen(panel, include_rejected=True)
    passed = {r.symbol for r in res if r.passed}
    rejected = {r.symbol for r in res if not r.passed}
    assert passed == {"UP"}
    assert rejected == {"DOWN", "SHORT"}
    # donnée manquante → rejetée par défaut (on_missing=fail), avec une raison lisible
    short = next(r for r in res if r.symbol == "SHORT")
    assert not short.passed and "above_sma200" in short.reason


def test_on_missing_pass_keeps_when_no_data():
    panel = {"SHORT": mkbars([100.0] * 30, "SHORT")}
    rule = _rule("above_sma200", ">=", 1, on_missing="pass")
    eng = ScreeningEngine({"filters": [rule]})
    res = eng.screen(panel)
    assert [r.symbol for r in res] == ["SHORT"]


def test_between_operator():
    panel = {
        "MILD": mkbars(_up(n=300, lo=100.0, hi=120.0), "MILD"),   # ret_12m faible
        "BUBBLE": mkbars(_up(n=300, lo=20.0, hi=400.0), "BUBBLE"),  # ret_12m énorme
    }
    eng = ScreeningEngine({"filters": [_rule("ret_12m", "between", [0.0, 0.5])]})
    passed = {r.symbol for r in eng.screen(panel)}
    assert "MILD" in passed
    assert "BUBBLE" not in passed


def test_dollar_volume_liquidity_filter():
    panel = {
        "LIQ": _bars_vol([100.0] * 30, 100_000, "LIQ"),   # 100 * 100k = 10 M$
        "ILLIQ": _bars_vol([100.0] * 30, 10, "ILLIQ"),     # 100 * 10 = 1 000 $
    }
    eng = ScreeningEngine({"filters": [_rule("dollar_volume", ">=", 5_000_000)]})
    assert {r.symbol for r in eng.screen(panel)} == {"LIQ"}


def test_scoring_orders_by_composite_momentum():
    panel = {
        "STEEP": mkbars(_up(n=320, lo=50.0, hi=300.0), "STEEP"),
        "SOFT": mkbars(_up(n=320, lo=50.0, hi=120.0), "SOFT"),
    }
    eng = ScreeningEngine({
        "filters": [_rule("above_sma200", ">=", 1)],
        "scoring": {"weights": {"momentum": 1.0}},
    })
    res = eng.screen(panel)
    assert [r.symbol for r in res] == ["STEEP", "SOFT"]
    assert res[0].score == res[0].score  # fini (pas NaN)
    assert res[0].score > res[1].score


def test_top_n_limits_results():
    panel = {f"S{i}": mkbars(_up(n=300, lo=50.0, hi=50.0 + i), f"S{i}")
             for i in range(5)}
    eng = ScreeningEngine({
        "filters": [_rule("above_sma200", ">=", 1)],
        "scoring": {"weights": {"momentum": 1.0}, "top_n": 2},
    })
    assert len(eng.screen(panel)) == 2


def test_unknown_metric_raises():
    panel = {"X": mkbars(_up(), "X")}
    eng = ScreeningEngine({"filters": [_rule("does_not_exist", ">", 0)]})
    with pytest.raises(ValueError, match="inconnue"):
        eng.screen(panel)


def test_unknown_operator_raises():
    panel = {"X": mkbars(_up(), "X")}
    eng = ScreeningEngine({"filters": [_rule("ret_12m", "≈", 0)]})
    with pytest.raises(ValueError, match="opérateur"):
        eng.screen(panel)


def test_no_filters_keeps_everything_and_scores():
    panel = {"A": mkbars(_up(n=320), "A"), "B": mkbars(_up(n=320, hi=150.0), "B")}
    eng = ScreeningEngine({"scoring": {"weights": {"momentum": 1.0}}})
    res = eng.screen(panel)
    assert {r.symbol for r in res} == {"A", "B"}


def test_from_yaml_loads_shipped_config():
    eng = ScreeningEngine.from_yaml("config/screening.yaml")
    assert eng.filters  # filtres présents
    assert eng.weights  # poids de scoring présents
    panel = {"UP": mkbars(_up(n=320), "UP"), "DOWN": mkbars(_down(n=320), "DOWN")}
    res = eng.screen(panel)  # ne doit pas lever
    assert all(r.passed for r in res)


def test_available_metrics_includes_factors_and_price():
    metrics = available_metrics()
    assert "momentum" in metrics
    assert "dollar_volume" in metrics
    assert "above_sma200" in metrics


def test_snapshot_screen_section_payload_shape():
    from apps.api.snapshot import _screen_section
    panel = {"UP": _bars_vol(_up(n=320, lo=50.0, hi=150.0), 100_000, "UP")}
    sec = _screen_section(
        panel, {"UP": "equity"}, {"UP": "Up Co"}, {"UP": "Tech"}, len(panel["UP"]) - 1
    )
    assert sec["available"] is True
    assert sec["filters"] and sec["weights"]
    assert sec["universe_size"] == 1
    assert sec["count"] >= 1
    row = sec["rows"][0]
    assert row["symbol"] == "UP"
    for k in ("rank", "score", "reason", "ret_12m", "dollar_volume", "sector"):
        assert k in row


def test_screen_section_excludes_non_investable_indices():
    from apps.api.snapshot import _screen_section
    panel = {
        "UP": _bars_vol(_up(n=320, lo=50.0, hi=150.0), 100_000, "UP"),
        "^KS11": _bars_vol(_up(n=320, lo=50.0, hi=160.0), 100_000, "^KS11"),  # indice
    }
    acmap = {"UP": "equity", "^KS11": "index"}
    sec = _screen_section(panel, acmap, {}, {}, len(panel["UP"]) - 1)
    syms = {r["symbol"] for r in sec["rows"]}
    assert "^KS11" not in syms              # indice non achetable → exclu
    assert sec["universe_size"] == 1        # seul l'investable est compté
    assert sec["excluded_non_investable"] == 1
