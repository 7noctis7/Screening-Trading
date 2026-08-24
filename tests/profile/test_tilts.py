"""L'amplitude suit la force de la PREUVE, jamais celle du signal.

C'est l'arbitrage central : un outil qui publie un Sharpe déflaté proche de zéro — donc aucun
alpha démontré — puis incline de quinze points sur cette même absence se contredit. Ces tests
figent la version bornée.
"""
import pytest

from packages.profile.investor import PLAFOND_DUR, Profil, allocation_strategique, budget_perte
from packages.profile.tilts import (
    AMPLITUDE_MAX, PREUVE_MIN, force_preuve, incliner, vues_depuis_regime,
)


def _p(**kw) -> Profil:
    base = dict(horizon_annees=15.0, perte_max_toleree=0.35, part_du_patrimoine=0.3)
    base.update(kw)
    return Profil(**base)


def _alloc(p=None):
    return allocation_strategique(p or _p())["poids"]


# --- La preuve, pas le signal ----------------------------------------------------------------

def test_un_signal_non_significatif_ne_produit_aucune_preuve():
    """|t| sous 2 : indistinguable de zéro, quel que soit l'échantillon."""
    assert force_preuve(t_stat=1.9, n_obs=5000)["force"] == 0.0


def test_un_t_eleve_sur_petit_echantillon_ne_compte_pas():
    """Un t de 3 sur 20 points est un accident de petit échantillon, pas une découverte."""
    r = force_preuve(t_stat=3.0, n_obs=20)
    assert r["force"] == 0.0 and "trop court" in r["motif"]


def test_labsence_de_mesure_vaut_preuve_nulle():
    """Ne pas savoir n'est pas savoir à moitié."""
    assert force_preuve(t_stat=None, n_obs=500)["force"] == 0.0
    assert force_preuve(t_stat=3.0, n_obs=None)["force"] == 0.0


def test_un_sharpe_deflate_nul_annule_la_preuve():
    """LE point : après correction du nombre d'essais, le signal n'est pas distinguable de la chance."""
    fort = force_preuve(t_stat=4.0, n_obs=500)["force"]
    corrige = force_preuve(t_stat=4.0, n_obs=500, dsr=0.01)
    assert fort == 1.0
    assert corrige["force"] < 0.05
    assert "chance" in corrige["motif"]


def test_la_preuve_croit_avec_le_t_et_lechantillon():
    a = force_preuve(t_stat=2.5, n_obs=100)["force"]
    b = force_preuve(t_stat=3.5, n_obs=100)["force"]
    c = force_preuve(t_stat=3.5, n_obs=500)["force"]
    assert a < b < c


# --- L'inclinaison est bornée ----------------------------------------------------------------

def test_sous_le_seuil_de_preuve_aucune_inclinaison():
    """Incliner « un peu » sur du bruit coûte du frottement pour une espérance nulle."""
    r = incliner(_alloc(), vues_depuis_regime("Expansion", "Risk-On"), PREUVE_MIN - 0.01, _p())
    assert not r["applique"] and r["inclinaisons"] == {}
    assert "insuffisante" in r["note"]


def test_lamplitude_ne_depasse_jamais_le_plafond():
    r = incliner(_alloc(), vues_depuis_regime("Expansion", "Risk-On"), 1.0, _p())
    assert r["amplitude"] <= AMPLITUDE_MAX + 1e-9
    assert max(abs(v) for v in r["inclinaisons"].values()) <= AMPLITUDE_MAX + 1e-6


def test_les_inclinaisons_somment_a_zero():
    """On déplace du poids, on n'en crée pas : sinon l'exposition dériverait à chaque calcul."""
    r = incliner(_alloc(), vues_depuis_regime("Expansion", "Risk-On"), 1.0, _p())
    assert abs(sum(r["inclinaisons"].values())) < 1e-6


def test_les_poids_inclines_somment_toujours_a_un():
    r = incliner(_alloc(), vues_depuis_regime("Contraction", "Risk-Off"), 0.9, _p())
    assert abs(sum(r["poids"].values()) - 1.0) < 1e-3


def test_les_plafonds_durs_du_profil_ne_sont_jamais_franchis():
    """Une conviction tactique ne rachète pas un risque de ruine."""
    p = _p(horizon_annees=40.0, perte_max_toleree=0.60, part_du_patrimoine=0.05)
    alloc = _alloc(p)
    vues = {"crypto": 1.0, "obligations": -1.0}
    r = incliner(alloc, vues, 1.0, p)
    for classe, cap in PLAFOND_DUR.items():
        assert r["poids"].get(classe, 0.0) <= cap + 1e-6


def test_une_inclinaison_qui_creverait_le_budget_est_annulee():
    """Une vue tactique ne consomme pas la marge de sécurité fixée par le profil."""
    p = _p(horizon_annees=30.0, perte_max_toleree=0.09)
    alloc = _alloc(p)
    r = incliner(alloc, {"actions_em": 1.0, "cash": -1.0}, 1.0, p)
    if not r["applique"]:
        assert "budget" in r["note"]
    else:
        from packages.profile.investor import perte_estimee
        assert perte_estimee(r["poids"]) <= budget_perte(p) + 1e-6


def test_une_vue_hors_allocation_est_ignoree_sans_planter():
    r = incliner(_alloc(), {"matieres_premieres": 1.0}, 1.0, _p())
    assert not r["applique"]


# --- Les vues de régime donnent une DIRECTION, pas une amplitude -----------------------------

def test_expansion_penche_vers_le_risque_contraction_vers_le_refuge():
    exp = vues_depuis_regime("Expansion", "Risk-On")
    con = vues_depuis_regime("Contraction", "Risk-On")
    assert exp["actions_dev"] > 0 > con["actions_dev"]
    assert con["obligations"] > 0 > exp["obligations"]


def test_risk_off_renforce_le_penchant_defensif():
    on = vues_depuis_regime("Expansion", "Risk-On")
    off = vues_depuis_regime("Expansion", "Risk-Off")
    assert off["actions_dev"] < on["actions_dev"]
    assert off["or"] > on["or"]


def test_regime_inconnu_ne_produit_aucune_vue():
    assert vues_depuis_regime(None, None) == {}
    assert vues_depuis_regime("", "") == {}
