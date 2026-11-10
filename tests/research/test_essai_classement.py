"""Essai figé de classement : la règle écrite est appliquée, rien n'est promu sans le gate.

Séries SYNTHÉTIQUES : la mécanique, jamais un chiffre de marché."""
import json
from pathlib import Path

import pytest
import yaml

from packages.research.essai_classement import (
    debut_commun,
    decision,
    gate,
    mesurer,
    nom_variante,
    variantes,
)
from packages.research.labo_classement import panneau
from tests.research.test_labo_classement import _donnees

ESSAI = Path(__file__).resolve().parents[2] / "config/essais/2026-11-10_momentum_residuel.yaml"


def _essai_court() -> dict:
    """L'essai réel, fenêtres raccourcies pour un panneau synthétique de 1 300 jours."""
    e = yaml.safe_load(ESSAI.read_text(encoding="utf-8"))
    e["variante_principale"]["estimation"] = 504
    e["voisines"] = [{"estimation": 504, "formation": 252, "saut": 21, "standardise": False},
                     {"estimation": 600, "formation": 252, "saut": 21, "standardise": True}]
    e["tirages_placebo"] = 20
    return e


def _registre(tmp_path, n: int) -> Path:
    p = tmp_path / "registre.jsonl"
    p.write_text("".join(json.dumps({"facteur": f"f{i}", "statut": "mesure"}) + "\n"
                         for i in range(n)), encoding="utf-8")
    return p


def test_l_essai_fige_declare_ce_qu_il_compte():
    e = yaml.safe_load(ESSAI.read_text(encoding="utf-8"))
    assert e["essais_comptes"] == len(variantes(e)) * len(e["horizons_seances"]) + 1
    assert nom_variante(e["variante_principale"]) == "e756_std" and debut_commun(e) == 756
    assert e["horizon_principal"] in e["horizons_seances"] and e["ordres"] == "aucun"


@pytest.fixture(scope="module")
def resultat(tmp_path_factory):
    led = _registre(tmp_path_factory.mktemp("r"), 500)
    return mesurer(panneau(_donnees(1, 0.0015)), _essai_court(), 0.0005,
                   chemin_ledger=led, n_nulles=200)


def test_le_nombre_d_essais_vient_du_registre_et_le_seuil_est_publie(resultat):
    g = resultat["gate"]
    assert g["n_essais"] == 500 and g["dsr_calcule"] is not None
    assert g["sharpe_exige_deployable"] > g["sharpe_exige_promouvable"] > 0


def test_les_compteurs_et_les_episodes_sont_publies(resultat):
    c = resultat["compteurs"]
    assert c["decisions"] > 100 and c["episodes_clos"] == resultat["episodes"]["n"]
    assert {"barres_manquantes", "ordres_non_executables", "rotation_mediane"} <= set(c)
    assert resultat["placebo"]["tirages"] == 20 and 0 < resultat["placebo"]["p"] <= 1


def test_un_candidat_qui_ne_bat_pas_le_temoin_n_est_pas_retenu(resultat):
    """Ici le signal planté est vu AUSSI par le momentum classique : l'écart apparié
    n'est pas positif, donc le facteur n'est pas retenu — battre zéro ne suffit pas."""
    d = resultat["decision"]
    assert d["facteur_retenu"] is False and d["strategie_promouvable"] is False
    assert any("écart d'IC" in m for m in d["motifs"])


def test_la_strategie_n_est_jamais_promouvable_sans_chaque_etage():
    e = _essai_court()
    cle = f"{nom_variante(e['variante_principale'])}"
    bon = {"available": True, "ecart_ic_moyen": 0.02, "p_signes": 0.01,
           "ecart_premiere_moitie": 0.01, "ecart_seconde_moitie": 0.03}
    ic = {f"{cle}:h{h}": {"ecart": bon} for h in e["horizons_seances"]}
    ok = {"promoted": True, "reasons": []}
    face = {"available": True, "ic95": [0.01, 0.05]}
    assert decision(ic, e, ok, {"survives": True}, face)["strategie_promouvable"]
    for casse in ((ic, {"promoted": False, "reasons": ["DSR"]}, {"survives": True}, face),
                  (ic, ok, {"survives": False}, face),
                  (ic, ok, {"survives": True}, {"available": True, "ic95": [-0.01, 0.05]})):
        d = decision(casse[0], e, casse[1], casse[2], casse[3])
        assert d["facteur_retenu"] and not d["strategie_promouvable"] and d["motifs"]


def test_sous_un_an_de_rendements_le_gate_dit_uncalibrated():
    import numpy as np
    assert gate(np.zeros(100), None, None)["status"] == "UNCALIBRATED"
