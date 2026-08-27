"""Le mandat du preset doit décrire le système RÉEL, sinon il ment.

Un mandat déclaratif qui diverge du code est pire que pas de mandat : il donne
l'illusion de l'audit. Ce test est le PONT — il échoue dès qu'une valeur par défaut
du moteur change sans que le mandat suive.

Format JSON et non YAML, délibérément. YAML 1.1 coerce `no` en booléen et distingue
mal `1` de `1.0` : sur un fichier dont le HASH est l'identité, ces conversions
silencieuses déplaceraient l'identité sans qu'on touche au sens.
"""

import inspect
import json
from pathlib import Path

import pytest

from packages.backtest.preset_weights import preset_latest_weights
from packages.mandate import Mandat, depuis_dict, exiger_valide

CHEMIN = Path(__file__).resolve().parents[2] / "config/mandats/preset_multi_actifs.json"

# Correspondance mandat → argument du moteur. Explicite, car les noms diffèrent :
# le mandat parle en CONTRAINTES (ce qu'on subit), le moteur en paramètres d'appel.
CORRESPONDANCE = {
    "contraintes.drawdown_max": "dd_target",
    "contraintes.poids_max_ligne": "max_weight",
    "contraintes.poids_min_ligne": "min_weight",
    "contraintes.nb_lignes_min": "min_names",
    "parametres.top_k": "top_k",
    "parametres.lookback": "lookback",
    "parametres.k_dd": "k_dd",
    "parametres.blackout_move": "blackout_move",
    "parametres.regime_gate": "regime_gate",
    "parametres.mom_tilt": "mom_tilt",
    "parametres.breadth_gate": "breadth_gate",
    "parametres.corr_tighten": "corr_tighten",
    "parametres.cov_denoise": "cov_denoise",
    "execution.bande_no_trade": "band",
}


@pytest.fixture(scope="module")
def mandat() -> Mandat:
    return depuis_dict(json.loads(CHEMIN.read_text(encoding="utf-8")))


def test_le_mandat_livre_est_recevable(mandat):
    exiger_valide(mandat)


def test_le_mandat_decrit_le_moteur_REEL(mandat):
    """Le pont. Rouge dès qu'une valeur par défaut du preset change sans le mandat."""
    defauts = {n: p.default
               for n, p in inspect.signature(preset_latest_weights).parameters.items()
               if p.default is not inspect.Parameter.empty}
    ecarts = []
    for chemin, arg in CORRESPONDANCE.items():
        section, cle = chemin.split(".")
        declare = getattr(mandat, section)[cle]
        reel = defauts[arg]
        if declare != reel or type(declare) is not type(reel):
            ecarts.append(f"{chemin} = {declare!r} mais {arg} = {reel!r}")
    assert not ecarts, "le mandat ment sur le moteur :\n  " + "\n  ".join(ecarts)


def test_aucun_parametre_du_moteur_oublie(mandat):
    """L'oubli est le mode de panne réel : un paramètre non déclaré n'entre pas dans
    le hash, donc le changer ne change pas l'identité — et l'audit ne le voit jamais."""
    ignores = {"quality", "asset_classes"}     # entrées de données, pas des réglages
    defauts = {n for n, p in inspect.signature(preset_latest_weights).parameters.items()
               if p.default is not inspect.Parameter.empty} - ignores
    couverts = set(CORRESPONDANCE.values())
    oublies = sorted(defauts - couverts)
    assert not oublies, f"paramètres hors mandat : {oublies}"


def test_l_identite_est_stable_sur_le_fichier_livre(mandat):
    """Verrou de non-régression du hash : si la forme canonique change, ce test le dit
    AVANT que des mandats déjà journalisés deviennent introuvables."""
    assert mandat.identite_courte() == "75854a2c223d9c04", mandat.identite_courte()


def test_renommer_le_mandat_livre_ne_bouge_pas_son_identite(mandat):
    assert mandat.renomme("Autre").identite() == mandat.identite()
