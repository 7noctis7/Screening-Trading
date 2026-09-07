"""Préférences sectorielles — des CONTRAINTES, dont le prix est mesuré et rendu."""
import numpy as np
import pytest

from packages.portfolio.preferences import appliquer, cout_de_la_contrainte

SECTEURS = ["Tech", "Tech", "Santé", "Crypto & Blockchain", "Commodités"]
POIDS = [0.40, 0.30, 0.05, 0.20, 0.05]


def test_sans_preference_rien_ne_bouge():
    out = appliquer(POIDS, SECTEURS, None)
    assert out["poids"] == POIDS and out["applique"] is False


def test_preferences_vides_ne_declenchent_rien():
    out = appliquer(POIDS, SECTEURS, {"exclure": [], "planchers": {}, "plafonds": {}})
    assert out["applique"] is False


def test_une_exclusion_met_le_secteur_a_zero_et_renormalise():
    out = appliquer(POIDS, SECTEURS, {"exclure": ["Crypto & Blockchain"]})
    assert out["poids"][3] == 0.0
    assert sum(out["poids"]) == pytest.approx(1.0)
    assert out["exclus"][0]["poids_retire"] == pytest.approx(0.20)


def test_l_exclusion_est_insensible_a_la_casse():
    """L'utilisateur tape ce qu'il lit à l'écran, pas une clé normalisée."""
    out = appliquer(POIDS, SECTEURS, {"exclure": ["crypto & BLOCKCHAIN"]})
    assert out["poids"][3] == 0.0


def test_un_plancher_monte_le_secteur_a_la_cible():
    out = appliquer(POIDS, SECTEURS, {"planchers": {"Santé": 0.25}})
    assert out["poids"][2] == pytest.approx(0.25)
    assert sum(out["poids"]) == pytest.approx(1.0)
    assert out["planchers"][0]["avant"] == pytest.approx(0.05)


def test_un_plancher_deja_satisfait_ne_touche_a_rien():
    out = appliquer(POIDS, SECTEURS, {"planchers": {"Tech": 0.50}})
    assert out["poids"] == POIDS and out["applique"] is False


def test_un_plafond_redescend_le_secteur_et_redistribue():
    out = appliquer(POIDS, SECTEURS, {"plafonds": {"Tech": 0.40}})
    assert out["poids"][0] + out["poids"][1] == pytest.approx(0.40)
    assert sum(out["poids"]) == pytest.approx(1.0)


def test_l_exclusion_passe_AVANT_le_plancher():
    """Sinon un plancher réintroduirait du poids sur un secteur qu'on vient d'exclure."""
    out = appliquer(POIDS, SECTEURS,
                    {"exclure": ["Crypto & Blockchain"], "planchers": {"Crypto & Blockchain": 0.30}})
    assert out["poids"][3] == 0.0
    assert out["non_satisfaits"][0]["raison"].startswith("secteur exclu")


def test_un_plancher_ne_ressuscite_pas_une_ligne_a_zero():
    """Monter au prorata des poids ACTUELS : une ligne que l'optimiseur a mise à zéro le
    reste, sinon la contrainte inventerait une position qu'il n'a pas voulue."""
    poids = [0.50, 0.50, 0.0]
    out = appliquer(poids, ["Tech", "Tech", "Santé"], {"planchers": {"Santé": 0.20}})
    assert out["poids"][2] == 0.0            # aucun membre du groupe n'avait de poids
    assert out["non_satisfaits"][0]["secteur"] == "santé"
    assert "ne crée pas" in out["non_satisfaits"][0]["raison"]


def test_exclure_TOUT_ne_produit_pas_un_portefeuille_vide():
    """Refuser l'unique secteur présent laisserait une somme nulle : on n'applique pas."""
    out = appliquer([0.5, 0.5], ["Tech", "Tech"], {"exclure": ["Tech"]})
    assert sum(out["poids"]) == pytest.approx(1.0)


def test_le_cout_est_rendu_avec_son_SIGNE():
    """Exclure un actif très volatil FAIT BAISSER la volatilité : parler de « surcoût »
    laisserait croire qu'une contrainte dégrade toujours le risque."""
    cov = np.diag(np.array([0.2, 0.25, 0.15, 0.70, 0.3]) ** 2)
    out = appliquer(POIDS, SECTEURS, {"exclure": ["Crypto & Blockchain"]})
    cout = cout_de_la_contrainte(POIDS, out["poids"], cov)
    assert cout["ecart_vol"] < 0                       # retirer la crypto calme le portefeuille
    assert cout["vol_apres"] < cout["vol_avant"]


def test_le_cout_est_positif_quand_on_force_un_actif_risque():
    cov = np.diag(np.array([0.10, 0.10, 0.60]) ** 2)
    poids = [0.5, 0.5, 0.0]
    force = appliquer([0.45, 0.45, 0.10], ["A", "A", "B"], {"planchers": {"B": 0.40}})
    cout = cout_de_la_contrainte([0.45, 0.45, 0.10], force["poids"], cov)
    assert cout["ecart_vol"] > 0
    assert poids[2] == 0.0                              # le vecteur d'origine n'est pas muté
