"""Gate mypy « aucune nouvelle erreur » : la clé ignore les lignes, le compte ne les ignore pas."""
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.mypy_baseline import (
    charger_reference,
    comparer,
    ecrire_reference,
    lire_sortie,
)

SORTIE = """\
packages/a.py:10: error: Missing return statement  [return]
packages/a.py:42: error: Missing return statement  [return]
packages/a.py:12: note: See https://mypy.rtfd.io/
packages/b.py:3: error: Name "x" already defined on line 1  [no-redef]
Found 3 errors in 2 files (checked 2 source files)
"""


def test_les_notes_et_le_resume_ne_sont_pas_des_erreurs():
    compte, _ = lire_sortie(SORTIE)
    assert sum(compte.values()) == 3


def test_ajouter_des_lignes_en_tete_ne_cree_aucune_erreur_nouvelle():
    """Toutes les erreurs du fichier descendent de deux lignes, y compris la ligne qu'un
    message cite : une clé qui contiendrait un numéro de ligne les verrait toutes neuves."""
    avant, _ = lire_sortie(SORTIE)
    decale = SORTIE.replace(":10:", ":12:").replace(":42:", ":44:").replace(
        ":3: error", ":5: error").replace("on line 1", "on line 3")
    apres, _ = lire_sortie(decale)
    assert comparer(apres, avant) == (Counter(), Counter())


def test_une_troisieme_occurrence_identique_est_une_erreur_nouvelle():
    """Deux erreurs identiques dans un fichier sont deux erreurs : en ajouter une doit échouer."""
    reference, _ = lire_sortie(SORTIE)
    plus = SORTIE + "packages/a.py:99: error: Missing return statement  [return]\n"
    actuel, brutes = lire_sortie(plus)
    nouvelles, corrigees = comparer(actuel, reference)
    assert sum(nouvelles.values()) == 1 and not corrigees
    (k,) = nouvelles
    assert brutes[k][-1].startswith("packages/a.py:99:")


def test_une_erreur_corrigee_ne_bloque_pas_et_est_signalee():
    reference, _ = lire_sortie(SORTIE)
    actuel, _ = lire_sortie(SORTIE.replace(
        'packages/b.py:3: error: Name "x" already defined on line 1  [no-redef]\n', ""))
    nouvelles, corrigees = comparer(actuel, reference)
    assert not nouvelles and sum(corrigees.values()) == 1


def test_la_reference_relue_est_celle_qui_a_ete_ecrite(tmp_path):
    compte, _ = lire_sortie(SORTIE)
    chemin = tmp_path / "ref.json"
    ecrire_reference(chemin, compte, "9.9.9")
    relu, version = charger_reference(chemin)
    assert relu == compte and version == "9.9.9"


def test_sans_reference_tout_est_nouveau(tmp_path):
    """Une référence absente ne doit pas tout laisser passer en silence."""
    compte, _ = lire_sortie(SORTIE)
    reference, version = charger_reference(tmp_path / "absente.json")
    assert version is None and sum(comparer(compte, reference)[0].values()) == 3


def test_la_reference_versionnee_est_lisible_et_coherente():
    """Le fichier commité : son total est la somme de ses comptes (pas de dérive manuelle)."""
    import json
    doc = json.loads((Path(__file__).resolve().parents[2] / "config" / "mypy_baseline.json")
                     .read_text(encoding="utf-8"))
    assert doc["total"] == sum(doc["erreurs"].values()) and doc["mypy"]
