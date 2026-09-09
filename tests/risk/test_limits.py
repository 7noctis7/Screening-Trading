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


def test_tous_les_appelants_declarent_leurs_vehicules_indiciels() -> None:
    """Le paramètre `index_names` est OPTIONNEL, donc oubliable — et il a été oublié.

    Le tableau de bord le passait (correctif d'audit du 06/07), le portefeuille preset
    non. Or c'est CE second rapport que lit le post-mortem : `incident_note` va chercher
    `portfolio.analysis.limits`. Résultat, « QQQ 50 % > plafond de nom 20 % » publié
    tous les jours sur un cœur core-satellite conforme, pendant que le tableau de bord,
    lui, ne signalait rien. Deux rapports, deux verdicts, sur le même portefeuille.

    On verrouille l'invariant à la source : dans snapshot.py, aucun appel au rapport de
    concentration ne se fait sans déclarer ses véhicules indiciels.
    """
    import re
    from pathlib import Path

    snap = Path(__file__).resolve().parents[2] / "apps" / "api" / "snapshot.py"
    src = snap.read_text(encoding="utf-8")
    # un appel = `concentration_report(` ou `_adaptive(` jusqu'à sa parenthèse fermante
    motif = r"concentration_report(?:_adaptive)?\((?:[^()]|\([^()]*\))*\)"
    appels = re.findall(motif, src)
    assert appels, "aucun appel trouvé — le motif a dérivé, corriger le test"
    muets = [a for a in appels if "index_names" not in a]
    assert not muets, f"appel sans index_names : {muets}"


def test_un_tracker_a_50_pct_n_est_pas_un_depassement_de_nom() -> None:
    """La règle métier que le test précédent protège, énoncée une fois.

    Un tracker n'est pas un émetteur : QQQ à 50 %, c'est cent noms, pas un. Le plafond
    de NOM (20 %) borne le risque idiosyncratique d'un émetteur unique ; l'appliquer à
    un indice large est une erreur de catégorie, pas une alerte.
    """
    from packages.risk.limits import concentration_report

    # satellites tous SOUS 20 % : QQQ est le seul enjeu du test
    poids = {"QQQ": 0.50, "AAPL": 0.18, "MSFT": 0.17, "NVDA": 0.15}

    sans = concentration_report(poids)
    assert [(b["label"], b["type"]) for b in sans["breaches"]] == [("QQQ", "nom")]

    avec = concentration_report(poids, index_names={"QQQ"})
    assert avec["breaches"] == [] and avec["ok"] is True

    # et le plafond indiciel RESTE un plafond : le reclassement n'est pas une dispense
    trop = concentration_report({"QQQ": 0.65, "AAPL": 0.18, "MSFT": 0.17},
                                index_names={"QQQ"})
    assert [(b["label"], b["type"], b["limit"]) for b in trop["breaches"]] == [
        ("QQQ", "indice", 0.60)]
