"""Contrat de la route `/api/portfolio/sentiment` — lu dans les SOURCES.

Trois choses ne doivent pas dériver sans qu'on le voie :
  1. le front et l'API appellent le MÊME chemin (une faute de frappe rend 404 en local
     et ne casse aucun test de calcul) ;
  2. la route est fermée aux appels non locaux, comme ses deux sœurs `/analyze` et
     `/recommend` — une route POST ouverte sur un repo public est un incident ;
  3. elle lit l'historique de sentiment (`delta`) et ne l'écrit pas
     (`record_and_delta`) : la promesse « aucune persistance » du contrat `/portfolio/*`.

Un test de source, pas d'exécution : importer `apps.api.main` construit tout le snapshot.
"""

from __future__ import annotations

from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
MAIN = (RACINE / "apps" / "api" / "main.py").read_text(encoding="utf-8")
API_TS = (RACINE / "apps" / "web" / "lib" / "api.ts").read_text(encoding="utf-8")
CORE = (RACINE / "packages" / "sentiment" / "portefeuille.py").read_text(encoding="utf-8")

CHEMIN = "/api/portfolio/sentiment"


def test_le_front_et_l_api_appellent_le_meme_chemin():
    assert f'@app.post("{CHEMIN}")' in MAIN
    assert CHEMIN in API_TS


def test_la_route_est_fermee_aux_appels_non_locaux():
    corps = MAIN[MAIN.index(f'@app.post("{CHEMIN}")'):]
    corps = corps[:corps.index("\nclass ")]
    assert "_webhook_authorized(request)" in corps, (
        "route POST sans garde locale : ouverte à quiconque atteint le port")


def test_le_moteur_LIT_l_historique_mais_ne_l_ECRIT_pas():
    assert "import delta" in CORE
    # on cherche l'APPEL, pas le mot : la docstring du module cite `record_and_delta`
    # précisément pour dire qu'il ne l'utilise pas.
    assert "record_and_delta(" not in CORE, (
        "un portefeuille de passage écrirait dans l'historique de sentiment du robot")


def test_le_repli_momentum_a_UNE_seule_definition():
    """Le snapshot du robot et l'analyse utilisateur doivent partager la formule.

    Deux copies de la même formule finissent par diverger sans que rien ne le signale —
    et les deux onglets afficheraient alors deux « tendances 3 mois » différentes pour
    le même actif.
    """
    snapshot = (RACINE / "apps" / "api" / "snapshot.py").read_text(encoding="utf-8")
    assert snapshot.count("score_momentum as _momentum") == 2
    assert "- 1) * 3.0)), 4)" not in snapshot, "la formule a été recopiée en dur"
