"""Le profil produit des CONTRAINTES vérifiables, pas une étiquette.

Ces tests figent les trois règles qui distinguent ce module d'un questionnaire de banque :
c'est la plus petite des deux mesures de risque qui lie, la sortie est un budget de perte
falsifiable, et l'allocation est vérifiée contre ce budget au lieu d'être promise.
"""
import pytest

from packages.profile.investor import (
    CREDIT_DIVERSIFICATION, PLAFOND_DUR, Profil, STRESS_HISTORIQUE,
    allocation_strategique, budget_perte, capacite, perte_estimee, risque_retenu, tolerance,
)


def _p(**kw) -> Profil:
    base = dict(horizon_annees=15.0, perte_max_toleree=0.35, part_du_patrimoine=0.3,
                besoin_liquidite=0.0, revenus_stables=True, experience_annees=5.0)
    base.update(kw)
    return Profil(**base)


# --- 1. C'est la PLUS PETITE des deux qui lie -------------------------------------------------

def test_un_horizon_court_bride_un_investisseur_audacieux():
    """L'erreur que ce module existe pour empêcher : laisser l'envie l'emporter sur la situation."""
    audacieux_mais_presse = _p(horizon_annees=2.0, perte_max_toleree=0.50, experience_annees=20)
    r = risque_retenu(audacieux_mais_presse)
    assert r["lie_par"] == "capacité"
    assert r["niveau"] == r["capacite"] < r["tolerance"]


def test_un_prudent_a_long_horizon_est_bride_par_sa_tolerance():
    prudent = _p(horizon_annees=30.0, perte_max_toleree=0.10, part_du_patrimoine=0.1)
    r = risque_retenu(prudent)
    assert r["lie_par"] == "tolérance"
    assert r["niveau"] == r["tolerance"] < r["capacite"]


def test_le_besoin_de_liquidite_raccourcit_l_horizon_effectif():
    """Une date cible lointaine ne protège pas si l'on doit retirer avant."""
    sans = capacite(_p(horizon_annees=20.0, besoin_liquidite=0.0))
    avec = capacite(_p(horizon_annees=20.0, besoin_liquidite=0.5))
    assert avec < sans


def test_investir_tout_son_patrimoine_reduit_la_capacite():
    """Sans matelas ailleurs, une baisse force à vendre au pire moment."""
    assert capacite(_p(part_du_patrimoine=0.9)) < capacite(_p(part_du_patrimoine=0.1))


def test_revenus_instables_reduisent_la_capacite():
    assert capacite(_p(revenus_stables=False)) < capacite(_p(revenus_stables=True))


# --- 2. La sortie est un budget, et il ne dépasse JAMAIS la déclaration -----------------------

def test_le_budget_ne_depasse_jamais_la_perte_declaree():
    """Le budget peut être plus prudent que ce qui est déclaré, jamais plus audacieux."""
    for perte in (0.05, 0.10, 0.20, 0.35, 0.50, 0.80):
        p = _p(horizon_annees=40.0, perte_max_toleree=perte, part_du_patrimoine=0.05)
        assert budget_perte(p) <= max(0.05, perte) + 1e-9, perte


def test_le_budget_croit_avec_le_risque_retenu():
    faible = budget_perte(_p(horizon_annees=2.0, perte_max_toleree=0.10))
    fort = budget_perte(_p(horizon_annees=30.0, perte_max_toleree=0.45, part_du_patrimoine=0.1))
    assert fort > faible


# --- 3. L'allocation est VÉRIFIÉE contre son budget, pas seulement promise --------------------

def test_toute_allocation_respecte_son_propre_budget():
    """Ce que les questionnaires oublient : vérifier que les poids tiennent dans la perte annoncée."""
    for h in (1.0, 3.0, 8.0, 20.0, 40.0):
        for perte in (0.05, 0.15, 0.30, 0.50):
            a = allocation_strategique(_p(horizon_annees=h, perte_max_toleree=perte))
            assert a["coherente"], (h, perte, a["perte_estimee"], a["budget_perte"])


def test_une_tolerance_faible_force_la_desensibilisation():
    """« Je n'accepte pas plus de 8 % de baisse » est incompatible avec une poche actions large."""
    a = allocation_strategique(_p(horizon_annees=30.0, perte_max_toleree=0.08))
    assert a["desensibilisations"] > 0
    assert a["poids"]["cash"] > 0.4
    assert "réduite vers le cash" in a["note"]


def test_les_poids_somment_a_un():
    for h in (1.0, 10.0, 40.0):
        a = allocation_strategique(_p(horizon_annees=h))
        assert abs(sum(a["poids"].values()) - 1.0) < 1e-3


def test_les_plafonds_durs_ne_sont_jamais_franchis():
    """Un risque de RUINE ne se compense pas par une bonne note ailleurs."""
    for h in (10.0, 25.0, 50.0):
        a = allocation_strategique(_p(horizon_annees=h, perte_max_toleree=0.60,
                                      part_du_patrimoine=0.05, experience_annees=30))
        for classe, cap in PLAFOND_DUR.items():
            assert a["poids"].get(classe, 0.0) <= cap + 1e-6, (classe, a["poids"])


def test_pas_de_crypto_pour_un_profil_prudent():
    a = allocation_strategique(_p(horizon_annees=3.0, perte_max_toleree=0.10))
    assert a["poids"].get("crypto", 0.0) == 0.0


# --- L'estimation de perte est délibérément conservatrice -------------------------------------

def test_le_credit_de_diversification_est_faible_et_assume():
    """En crise, les corrélations convergent vers 1 : un large crédit se tromperait au pire moment."""
    assert CREDIT_DIVERSIFICATION <= 0.20


def test_perte_estimee_encadree_par_les_pires_baisses():
    tout_actions = {"actions_dev": 1.0}
    assert perte_estimee(tout_actions) == pytest.approx(
        STRESS_HISTORIQUE["actions_dev"] * (1 - CREDIT_DIVERSIFICATION))
    assert perte_estimee({"cash": 1.0}) == 0.0


def test_une_allocation_100_actions_ne_peut_pas_promettre_15_pourcent():
    """Le contrôle de cohérence en une phrase : les actions ont fait -55 % en 2008."""
    assert perte_estimee({"actions_dev": 1.0}) > 0.30
