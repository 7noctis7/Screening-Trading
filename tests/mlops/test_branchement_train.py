"""Le registre est-il RÉELLEMENT sur le chemin de production ?

Même distinction que pour le portail de risque et la garde journalière : la logique est
testée ailleurs, ici on teste le CÂBLAGE. Un registre qu'on branche « plus tard » n'est
jamais branché — il devient de la cérémonie, on cesse de l'alimenter, et six mois après il
décrit un état qui n'existe plus. C'est le risque nommé dans `docs/AI_ARCHITECTURE_AUDIT.md`.
"""

import pathlib

RACINE = pathlib.Path(__file__).resolve().parents[2]
TRAIN = RACINE / "scripts" / "train_model.py"


def _src() -> str:
    return TRAIN.read_text(encoding="utf-8")


def test_le_registre_est_appele_par_l_entrainement():
    src = _src()
    assert "from packages.mlops.registre import Registre" in src
    assert "_tracer(" in src


def test_la_trace_vient_APRES_la_decision_de_promotion():
    """Le registre EXÉCUTE une décision, il ne la prend pas. L'inverser ferait du registre
    un deuxième juge — deux autorités qui peuvent diverger sans que rien ne le dise."""
    src = _src()
    assert src.index("promu, raison = _decider_promotion(") < src.index("trace = _tracer(")


def test_la_trace_ne_fait_jamais_echouer_un_entrainement_reussi():
    src = _src()
    bloc = src.split("trace = _tracer(", 1)[1].split("print(", 1)[0]
    assert "except Exception" in bloc


def test_mais_un_echec_de_trace_se_DIT():
    """Non bloquant ne veut pas dire muet : une traçabilité qui s'éteint en silence est
    pire que pas de traçabilité, parce qu'on croit l'avoir."""
    src = _src()
    assert "registre non écrit" in src
    assert "Registre :" in src


def test_l_entrainement_enregistre_l_empreinte_de_l_artefact():
    """Sans elle, la promotion ne pourra pas revérifier que le fichier n'a pas changé."""
    src = _src()
    assert "artefact_sha256=sha256_fichier(artefact)" in src


def test_un_candidat_refuse_est_enregistre_comme_rejete():
    """Un refus est une information : le perdre, c'est risquer de réessayer le même
    modèle sans savoir qu'il a déjà été écarté."""
    src = _src()
    bloc = src.split("def _tracer(", 1)[1].split("\ndef ", 1)[0]
    assert "reg.rejeter(" in bloc and "reg.promouvoir(" in bloc


def test_la_faiblesse_de_l_empreinte_dataset_est_ECRITE():
    """`_ml_section` ne rend pas les barres brutes : on hache la DESCRIPTION du run, ce qui
    est plus faible qu'un hash des données. Une limite tue devient un mensonge."""
    src = _src()
    bloc = src.split("def _tracer(", 1)[1].split("\ndef ", 1)[0]
    assert "plus faible" in bloc


def test_la_cli_exige_un_motif():
    """Un registre sans motifs ne répond pas à « pourquoi ce modèle est-il en production ? »"""
    cli = (RACINE / "scripts" / "registre_modeles.py").read_text(encoding="utf-8")
    assert "--motif est obligatoire" in cli


def test_la_cli_signale_un_modele_entraine_depuis_un_arbre_sale():
    cli = (RACINE / "scripts" / "registre_modeles.py").read_text(encoding="utf-8")
    assert "-sale" in cli and "non reproductible" in cli


def test_make_registre_existe():
    mk = (RACINE / "Makefile").read_text(encoding="utf-8")
    assert "registre:" in mk and "scripts/registre_modeles.py" in mk
