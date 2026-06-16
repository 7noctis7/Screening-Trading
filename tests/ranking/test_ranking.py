"""Ranking validé sur des séries DÉTERMINISTES (pentes contrôlées) → ordre garanti."""
from datetime import datetime, timedelta, timezone
from packages.core.models import Bar
from packages.ranking import RankingEngine, factor_calcs

CFG = {
    "weights": {"default": {"momentum": 0.5, "trend": 0.5}},
    "class_applicability": {"forex": ["momentum", "trend"]},
}


def _ramp(symbol, growth, n=300):
    """Croissance composée constante → momentum/trend strictement monotones en growth."""
    t0 = datetime(2022, 1, 1, tzinfo=timezone.utc)
    bars, p = [], 100.0
    for i in range(n):
        p *= (1 + growth)
        bars.append(Bar(symbol, "1d", t0 + timedelta(days=i), p, p, p, p, 1000.0))
    return bars


def test_higher_growth_ranks_higher():
    panel, cls = {}, {}
    for i, sym in enumerate(["A", "B", "C", "D"]):
        panel[sym] = _ramp(sym, growth=0.0002 * (i + 1))  # A<B<C<D
        cls[sym] = "equity"
    ranked = RankingEngine(CFG, cls).rank(panel, t=10**9, top_n=4)
    assert [r.symbol for r in ranked] == ["D", "C", "B", "A"]
    assert ranked[0].score > ranked[-1].score


def test_contributions_explain_score():
    panel = {"A": _ramp("A", 0.0001), "B": _ramp("B", 0.0005)}
    cls = {"A": "equity", "B": "equity"}
    ranked = RankingEngine(CFG, cls).rank(panel, t=10**9)
    for r in ranked:
        assert abs(sum(r.contributions.values()) / sum(CFG["weights"]["default"].values())
                   - r.score) < 1e-9
        assert r.reason  # non vide


def test_class_applicability_restricts_factors():
    cfg = {
        "weights": {"default": {"momentum": 0.4, "trend": 0.3, "value": 0.3}},
        "class_applicability": {"forex": ["momentum", "trend"]},
    }
    panel = {"X": _ramp("X", 0.0003), "Y": _ramp("Y", 0.0001)}
    cls = {"X": "forex", "Y": "forex"}
    ranked = RankingEngine(cfg, cls).rank(panel, t=10**9)
    # 'value' n'est pas applicable au forex → absent des contributions
    assert all("value" not in r.contributions for r in ranked)


def test_factor_calcs_registered():
    assert {"momentum", "trend", "low_vol"} <= set(factor_calcs.names())
