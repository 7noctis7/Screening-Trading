"""Un script qui importe un nom ABSENT de `snapshot` est une commande morte.

`scripts/*.py` importe volontiers des noms STDLIB *à travers* `apps.api.snapshot` —
`datetime`, `timedelta`, `timezone` — parce qu'ils y sont visibles. C'est un
ré-export implicite : rien ne le déclare, rien ne le protège.

Le jour où `snapshot` est modernisé (`timezone.utc` → `UTC`), le nom disparaît et
TREIZE scripts lèvent `ImportError` au premier appel. Mesuré le 10/09 : `make preset-lab`
était mort depuis le commit 2b37ba8, avec `make train`, `make backtest-ml`,
`make calibrate-preset`, `make ledger-sweep`… Personne ne s'en était aperçu, parce que
personne ne les avait relancés.

Ce test lit la SOURCE et confronte chaque nom importé à ce que le module expose
réellement. Il ne teste pas ce que les scripts font — il teste qu'ils démarrent.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[2]
SCRIPTS = sorted((RACINE / "scripts").glob("*.py"))


def _noms_importes(source: str, module: str) -> list[str]:
    """Noms importés depuis `module`, y compris dans les imports différés (in-function)."""
    try:
        arbre = ast.parse(source)
    except SyntaxError:
        return []
    return [alias.name for noeud in ast.walk(arbre)
            if isinstance(noeud, ast.ImportFrom) and noeud.module == module
            for alias in noeud.names]


@pytest.mark.parametrize("chemin", SCRIPTS, ids=lambda p: p.name)
def test_les_noms_importes_de_snapshot_EXISTENT(chemin: Path):
    noms = _noms_importes(chemin.read_text(encoding="utf-8"), "apps.api.snapshot")
    if not noms:
        pytest.skip("n'importe rien de snapshot")
    import apps.api.snapshot as snap
    manquants = sorted({n for n in noms if not hasattr(snap, n)})
    assert not manquants, (
        f"{chemin.name} importe {manquants} de `apps.api.snapshot`, qui ne les expose "
        "pas : la commande lève ImportError au premier appel. Importer les noms stdlib "
        "depuis `datetime`, pas à travers un module applicatif.")


def test_le_test_a_bien_une_cible():
    """Garde-fou : si le repérage des imports casse, tout serait vert pour rien."""
    concernes = [c for c in SCRIPTS
                 if _noms_importes(c.read_text(encoding="utf-8"), "apps.api.snapshot")]
    assert len(concernes) >= 10, (
        f"seulement {len(concernes)} script(s) repéré(s) — le parseur a perdu sa cible")
