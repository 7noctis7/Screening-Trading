"""Verrou du découpage de `apps/api/snapshot.py` (31/10) — même principe que `preset_*`.

`snapshot.py` avait dérivé à 3 300 lignes. Il est découpé en morceaux sous 400 lignes dans
`apps/api/snapshot_parts/`, texte des définitions inchangé, et reste la façade : une
trentaine de scripts et de tests font `from apps.api.snapshot import X`. Ces tests
empêchent la re-dérive et la perte silencieuse d'un ré-export.
"""
import ast
import importlib

import pytest

from tests.api.source_snapshot import API, fichiers_snapshot, source_snapshot

PARTS = sorted((API / "snapshot_parts").glob("*.py"))
MAX_LIGNES_FICHIER = 400


def _noms_definis(chemin) -> set[str]:
    noms = set()
    for n in ast.parse(chemin.read_text(encoding="utf-8")).body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            noms.add(n.name)
        elif isinstance(n, ast.Assign):
            noms |= {t.id for t in n.targets if isinstance(t, ast.Name)}
    return noms


def test_il_y_a_bien_des_morceaux():
    """Garde-fou du garde-fou : si le glob ne trouve rien, les tests ci-dessous sont vides."""
    assert len(PARTS) >= 10 and len(fichiers_snapshot()) == len(PARTS) + 1


@pytest.mark.parametrize("chemin", [API / "snapshot.py", *PARTS], ids=lambda p: p.name)
def test_fichier_sous_le_plafond(chemin):
    n = len(chemin.read_text(encoding="utf-8").splitlines())
    assert n < MAX_LIGNES_FICHIER, f"{chemin.name} : {n} lignes ≥ {MAX_LIGNES_FICHIER}"


@pytest.mark.parametrize("chemin", PARTS, ids=lambda p: p.name)
def test_la_facade_reexporte_chaque_nom(chemin):
    """Un nom défini dans un morceau mais absent de la façade casserait ses importeurs."""
    snapshot = importlib.import_module("apps.api.snapshot")
    module = importlib.import_module(f"apps.api.snapshot_parts.{chemin.stem}")
    for nom in _noms_definis(chemin):
        assert getattr(snapshot, nom) is getattr(module, nom), f"{nom} non ré-exporté"


@pytest.mark.parametrize("chemin", PARTS, ids=lambda p: p.name)
def test_un_morceau_n_importe_jamais_la_facade(chemin):
    """La façade importe les morceaux ; l'inverse créerait un cycle d'import.

    Lu sur l'AST, y compris dans les fonctions : les docstrings citent la façade."""
    for n in ast.walk(ast.parse(chemin.read_text(encoding="utf-8"))):
        if isinstance(n, ast.ImportFrom):
            assert n.module != "apps.api.snapshot", f"ligne {n.lineno}"
            assert not (n.module == "apps.api" and any(a.name == "snapshot" for a in n.names))
        elif isinstance(n, ast.Import):
            assert all(a.name != "apps.api.snapshot" for a in n.names), f"ligne {n.lineno}"


def test_les_tests_qui_lisent_le_source_voient_tous_les_morceaux():
    """`build_snapshot` est dans la façade, ses étapes dans les morceaux : les deux visibles."""
    src = source_snapshot()
    assert "def build_snapshot(" in src and "def _sb_39(" in src and "def _load_prices(" in src
