"""Tests du gate de promotion (Checker unique)."""

from packages.research.gate import promotion_verdict


def test_all_pass_promotes():
    v = promotion_verdict(dsr=0.8, pbo=0.3, edge=0.05, placebo_p=0.01)
    assert v["promoted"] and v["reasons"] == []
    assert v["checks"] == {"placebo": True, "dsr": True, "pbo": True, "edge": True}


def test_any_fail_rejects_with_reason():
    # le cas réel PEAD small/mid : DSR 0, PBO 0.76 → rejeté
    v = promotion_verdict(dsr=0.0, pbo=0.758, edge=0.059)
    assert not v["promoted"]
    joined = " ".join(v["reasons"])
    assert "DSR" in joined and "PBO" in joined


def test_missing_controls_are_ignored_but_one_required():
    # seul placebo mesuré et OK → promu (event-study seul)
    assert promotion_verdict(placebo_p=0.02)["promoted"] is True
    # aucun contrôle mesuré → JAMAIS promu (pas de feu vert sur rien)
    assert promotion_verdict()["promoted"] is False


def test_thresholds_overridable():
    assert promotion_verdict(dsr=0.6, dsr_min=0.7)["promoted"] is False
    assert promotion_verdict(dsr=0.6, dsr_min=0.5)["promoted"] is True
