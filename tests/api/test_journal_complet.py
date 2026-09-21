"""Le journal UI montre tout le registre sans dépendre du réseau courtier."""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
API = ROOT / "apps" / "api" / "main.py"
PAGE = ROOT / "apps" / "web" / "app" / "journal" / "page.tsx"


def _source_route() -> str:
    tree = ast.parse(API.read_text(encoding="utf-8"))
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                and n.name == "journal_roundtrips")
    return ast.unparse(node)


def test_le_journal_ne_filtre_plus_les_imports_courtier():
    src = _source_route()
    assert "j.all()" in src
    assert "j.all(legacy=False)" not in src
    assert "legacy_ids" in src


def test_le_journal_ne_declenche_ni_snapshot_ni_appel_courtier():
    tree = ast.parse(_source_route())
    calls = {n.func.id for n in ast.walk(tree) if isinstance(n, ast.Call)
             and isinstance(n.func, ast.Name)}
    for interdit in ("_snap", "_prix_courants", "_qtes_courtier"):
        assert interdit not in calls


def test_la_page_n_affirme_plus_afficher_un_sous_ensemble():
    page = PAGE.read_text(encoding="utf-8")
    assert "Historique local complet" in page
    assert "Périmètre affiché ≠ compte" not in page
    assert "historique Alpaca" in page
