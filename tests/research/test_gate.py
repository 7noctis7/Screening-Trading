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


def test_le_DSR_est_CALCULE_jamais_fourni(monkeypatch):
    """LE trou que ferme ce branchement. `promotion_verdict` reçoit `dsr` comme un
    nombre : c'est l'appelant qui a choisi le nombre d'essais dont il déflate. Or le
    DSR n'a de sens que si ce nombre est COMPTÉ. `verdict_hors_echantillon` le lit du
    ledger, et n'expose AUCUN paramètre pour le fournir — un garde-fou contournable
    par un argument nommé n'en est pas un."""
    import inspect

    from packages.research.gate import verdict_hors_echantillon
    params = inspect.signature(verdict_hors_echantillon).parameters
    assert "dsr" not in params and "n_essais" not in params

    monkeypatch.setattr("packages.research.protocole_oos.essais_du_ledger",
                        lambda _c=None: 40)
    v = verdict_hors_echantillon(sharpe_oos=0.05, n_obs_oos=500, pbo=0.2, edge=0.01,
                                 placebo_p=0.01)
    assert v["n_essais"] == 40
    assert v["dsr_calcule"] is not None
    assert "deployable" in v


def test_plus_d_essais_deflate_davantage(monkeypatch):
    """La propriété qui donne son sens au DSR : chercher plus longtemps doit RENDRE la
    porte plus dure, sinon compter les essais ne sert à rien."""
    from packages.research.gate import verdict_hors_echantillon

    def _dsr(n):
        monkeypatch.setattr("packages.research.protocole_oos.essais_du_ledger",
                            lambda _c=None: n)
        return verdict_hors_echantillon(sharpe_oos=0.06, n_obs_oos=500)["dsr_calcule"]

    assert _dsr(2) > _dsr(500)


def test_promotion_verdict_reste_INCHANGEE():
    """Trois appelants s'en servent ; rien n'oblige un backtest déjà écrit à migrer."""
    import inspect

    from packages.research.gate import promotion_verdict
    assert "dsr" in inspect.signature(promotion_verdict).parameters
    assert promotion_verdict(dsr=0.9, pbo=0.1, edge=0.02)["promoted"] is True
