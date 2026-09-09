"""Péremption d'un symbole : mesurée sur les PRIX locaux, jamais sur un 404 de fournisseur."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.auditer_univers_perime import classer


def test_le_seuil_est_RELATIF_a_la_barre_la_plus_fraiche():
    """Un seuil absolu déclarerait tout l'univers périmé après une semaine sans ingestion :
    la référence doit bouger avec la base, pas avec l'horloge."""
    tri = classer({"VIVANT": "2026-09-05", "MORT": "2019-03-01"}, seuil=10)
    assert tri["fraiche"] == "2026-09-05" and tri["limite"] == "2026-08-26"
    assert tri["vivants"] == ["VIVANT"] and tri["perimes"] == ["MORT"]


def test_une_base_vieille_de_six_mois_ne_declare_rien_de_perime():
    """Tous les symboles s'arrêtent le même jour : c'est l'ingestion qui dort, pas eux."""
    tri = classer({"A": "2026-03-02", "B": "2026-03-02", "C": "2026-03-01"}, seuil=10)
    assert tri["perimes"] == [] and set(tri["vivants"]) == {"A", "B", "C"}


def test_un_symbole_sans_barre_n_est_ni_vivant_ni_perime():
    """Ne pas savoir n'est pas savoir à moitié : il part dans sa propre catégorie."""
    tri = classer({"A": "2026-09-05", "JAMAIS_INGERE": None}, seuil=10)
    assert tri["muets"] == ["JAMAIS_INGERE"]
    assert "JAMAIS_INGERE" not in tri["vivants"] + tri["perimes"]


def test_aucune_barre_du_tout_rend_le_verdict_IMPOSSIBLE():
    """Sans référence, on ne tranche pas — on le dit, on ne suppose pas le pire."""
    tri = classer({"A": None, "B": None})
    assert tri["mesurable"] is False and tri["perimes"] == []
    assert tri["muets"] == ["A", "B"]


def test_la_borne_du_seuil_est_inclusive():
    tri = classer({"PILE": "2026-08-26", "JUSTE_AVANT": "2026-08-25",
                   "REF": "2026-09-05"}, seuil=10)
    assert "PILE" in tri["vivants"] and "JUSTE_AVANT" in tri["perimes"]
