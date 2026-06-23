"""Tests SPC / Six Sigma (qualité des données)."""

from packages.data.spc import cusum, dpmo, p_chart, sigma_level


def test_p_chart_basic_limits():
    out = p_chart(5, 1000)
    assert out["available"] and out["p"] == 0.005
    assert out["lcl"] <= out["p"] <= out["ucl"]
    assert out["ucl"] <= 1.0 and out["lcl"] >= 0.0


def test_p_chart_zero_defects():
    out = p_chart(0, 500)
    assert out["p"] == 0.0 and out["ucl"] == 0.0 and out["lcl"] == 0.0


def test_p_chart_empty():
    assert p_chart(0, 0)["available"] is False


def test_dpmo():
    assert dpmo(0, 1000) == 0.0
    assert dpmo(1, 1_000_000) == 1.0
    assert dpmo(0, 0) == 0.0


def test_sigma_level_monotone_and_anchors():
    # moins de défauts → niveau sigma plus élevé
    assert sigma_level(3.4) > sigma_level(66_800)
    assert sigma_level(0.0) == 6.0          # rendement parfait → cap 6σ
    # ~6σ pour 3,4 DPMO (convention décalage 1,5σ), tolérance large
    assert 5.5 <= sigma_level(3.4) <= 6.0
    # ~3σ pour ~66 800 DPMO
    assert 2.8 <= sigma_level(66_800) <= 3.2


def test_cusum_flags_level_shift():
    # série stable puis saut de niveau → alarme
    stable = [0.0] * 30
    shifted = [5.0] * 30
    out = cusum(stable + shifted, target=0.0, k=0.5, h=5.0)
    assert out["available"] and out["n_alarms"] > 0
    assert out["alarms"][0] >= 30          # l'alarme survient APRÈS le saut


def test_cusum_no_alarm_when_on_target():
    out = cusum([0.0, 0.1, -0.1, 0.05, -0.05] * 10, target=0.0, k=0.5, h=5.0)
    assert out["available"] and out["n_alarms"] == 0


def test_cusum_too_short():
    assert cusum([1.0], target=0.0)["available"] is False
