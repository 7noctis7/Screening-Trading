"""Immunisation NLP : négation à portée, garde-fou sémantique, point-in-time, sorties convexes."""

from datetime import datetime, timezone

from packages.execution.costs import stochastic_slippage_bps
from packages.risk.stops import convex_stops, vol_scaled_size
from packages.sentiment.lexicon import score_detail, score_text
from packages.sentiment.pit import alpha_decay_weight, usable_at
from packages.sentiment.risk_gate import semantic_gate


def test_negation_within_window():
    # « pas une mauvaise surprise » → positif malgré « bad » (négation à portée)
    assert score_text("this is not a weak quarter") > 0
    assert score_text("weak guidance and profit warning") < 0


def test_confidence_drops_on_contrast_and_hedge():
    plain = score_detail("strong beat, record profit")
    hedged = score_detail("might possibly beat but downgrade risk")
    assert plain["confidence"] > hedged["confidence"]


def test_semantic_gate_blocks_low_confidence_and_is_asymmetric():
    blocked = semantic_gate(0.9, confidence=0.2, n_sources=5)      # ambigu → bloqué
    assert blocked["impact"] == 0.0 and blocked["blocked"]
    pos = semantic_gate(1.0, confidence=1.0, n_sources=5, cap_pos=0.05, cap_neg=0.10)
    neg = semantic_gate(-1.0, confidence=1.0, n_sources=5, cap_pos=0.05, cap_neg=0.10)
    assert pos["impact"] == 0.05 and neg["impact"] == -0.10        # asymétrie défensive


def test_semantic_gate_requires_corroboration():
    one = semantic_gate(0.1, 1.0, n_sources=1, k_required=3)       # score modéré (hors plafond)
    three = semantic_gate(0.1, 1.0, n_sources=3, k_required=3)
    assert one["corroboration"] < three["corroboration"]
    assert three["impact"] > one["impact"]


def test_news_pit_no_lookahead():
    bar = datetime(2024, 1, 2, 16, 0, tzinfo=timezone.utc)
    after = datetime(2024, 1, 2, 16, 1, tzinfo=timezone.utc)
    before = datetime(2024, 1, 2, 15, 0, tzinfo=timezone.utc)
    assert usable_at(before, bar) is True
    assert usable_at(after, bar) is False                          # 16:01 inutilisable au close 16:00


def test_alpha_decay_halves():
    t0 = datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)
    t1 = datetime(2024, 1, 1, 10, 30, tzinfo=timezone.utc)
    assert abs(alpha_decay_weight(t0, t1, half_life_min=30) - 0.5) < 1e-6


def test_stochastic_slippage_explodes_with_vol():
    calm = stochastic_slippage_bps(3.0, vol_ratio=1.0)
    shock = stochastic_slippage_bps(3.0, vol_ratio=3.0)
    assert shock > calm and calm == 3.0


def test_convex_stops_widen_with_text_vol_and_size_shrinks():
    s0 = convex_stops(100, atr=2.0, text_vol=0.0)
    s1 = convex_stops(100, atr=2.0, text_vol=1.0)
    assert s1["stop_dist"] > s0["stop_dist"]                       # stop plus large si incertitude
    assert s1["target"] - 100 > 100 - s1["stop"]                  # convexité (target > stop)
    assert vol_scaled_size(0.1, 0.04, text_vol=1.0) < vol_scaled_size(0.1, 0.04, text_vol=0.0)
