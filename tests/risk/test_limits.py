from packages.risk.limits import (
    concentration_report,
    concentration_report_adaptive,
    correlation_aware_caps,
)


def test_breach_name():
    r = concentration_report({"A": 0.5, "B": 0.5}, max_name=0.20)
    assert not r["ok"] and any(b["type"] == "nom" for b in r["breaches"])


def test_hhi_and_effective_n():
    r = concentration_report({"A": 0.25, "B": 0.25, "C": 0.25, "D": 0.25})
    assert abs(r["hhi"] - 0.25) < 1e-9 and abs(r["effective_n"] - 4.0) < 0.1


def test_sector_breach():
    r = concentration_report({"A": 0.1}, {"Tech": 0.6}, max_sector=0.40)
    assert any(b["type"] == "secteur" for b in r["breaches"])


def test_correlation_aware_caps_tightens_on_breakdown():
    breakdown = {"available": True, "avg_corr_stress": 0.9,
                 "diversification_breakdown": True}
    mn, ms, tight = correlation_aware_caps(0.20, 0.40, breakdown)
    assert tight and mn == 0.10 and ms == 0.20
    # corr de stress élevée sans flag → resserre quand même
    _, _, t2 = correlation_aware_caps(0.20, 0.40,
                                      {"available": True, "avg_corr_stress": 0.8})
    assert t2 is True
    # pas de breakdown / pas de report → plafonds inchangés
    mn3, ms3, t3 = correlation_aware_caps(0.20, 0.40,
                                          {"available": True, "avg_corr_stress": 0.3})
    assert (mn3, ms3, t3) == (0.20, 0.40, False)
    assert correlation_aware_caps(0.20, 0.40, None) == (0.20, 0.40, False)


def test_adaptive_report_breaches_only_when_tightened():
    pos = {"A": 0.15, "B": 0.15, "C": 0.20, "D": 0.50}
    calm = concentration_report_adaptive(pos, None,
                                         {"available": True, "avg_corr_stress": 0.3})
    # à 0.20, seul D (0.50) dépasse
    assert not calm["tightened"] and [b["label"] for b in calm["breaches"]] == ["D"]
    stress = concentration_report_adaptive(
        pos, None, {"available": True, "diversification_breakdown": True})
    # à 0.10 resserré, A/B/C/D dépassent tous
    assert stress["tightened"] and len(stress["breaches"]) == 4


def test_index_vehicle_uses_dedicated_cap():
    """Fix audit 06/07 : un cœur indiciel (QQQ 45 %) ne doit PAS déclencher la limite
    20 %/nom (stock-picking) — mais un dépassement du plafond indice (60 %) doit alerter."""
    from packages.risk.limits import concentration_report
    w = {"QQQ": 0.45, "NVDA": 0.10, "AAPL": 0.10, "BTC/USD": 0.35}
    rep = concentration_report(w, max_name=0.20, index_names={"QQQ"})
    labels = {(b["type"], b["label"]) for b in rep["breaches"]}
    assert ("nom", "QQQ") not in labels and ("indice", "QQQ") not in labels
    assert ("nom", "BTC/USD") in labels          # 35 % sur UN actif non-indiciel = vraie alerte
    rep2 = concentration_report({"QQQ": 0.70}, index_names={"QQQ"})
    assert rep2["breaches"][0]["type"] == "indice"   # au-delà de 60 %, l'indice alerte aussi
