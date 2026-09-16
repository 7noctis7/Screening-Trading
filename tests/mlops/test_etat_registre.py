"""L'état des modèles vient du REGISTRE, et survit au retrait de la chaîne NLP.

Ce test vivait dans `tests/nlp/`. Il n'y avait pas sa place : il décrit le registre ML,
pas un fournisseur de LLM. Le voisinage aurait fait disparaître la version du modèle
affichée sur le site le jour où la chaîne NLP a été retirée.
"""

import pathlib

from packages.mlops.etat import etat_modeles

RACINE = pathlib.Path(__file__).resolve().parents[2]


def test_l_etat_des_modeles_vient_du_registre_pas_d_une_constante():
    """Un numéro de version écrit en dur se détache de ce qu'il désigne (ADR-0154)."""
    src = (RACINE / "packages" / "mlops" / "etat.py").read_text(encoding="utf-8")
    assert "from packages.mlops.registre import Registre" in src
    e = etat_modeles()
    assert e["disponible"] is True
    for cle in ("production", "dataset_hash", "git_commit", "candidats", "archives",
                "reproductible", "incoherences"):
        assert cle in e


def test_un_registre_indisponible_ne_fait_PAS_tomber_l_etat_IA():
    import packages.mlops.registre as R
    original = R.Registre
    R.Registre = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("disque"))
    try:
        e = etat_modeles()
        assert e["disponible"] is False and "disque" in e["motif"]
    finally:
        R.Registre = original


def test_la_route_du_registre_survit_au_retrait_de_la_chaine_NLP():
    """Les routes IA d'origine restent : retirer la chaîne locale ne devait toucher
    QUE ce qui appelait un fournisseur de LLM."""
    src = (RACINE / "apps" / "api" / "main.py").read_text(encoding="utf-8")
    for route in ("/api/ai/status", "/api/ai/diagnostic", "/api/ai/commentary",
                  "/api/ai/metrics", "/api/ai/modeles"):
        assert route in src
    assert "packages.nlp" not in src, "plus aucune trace de la chaîne NLP locale"
