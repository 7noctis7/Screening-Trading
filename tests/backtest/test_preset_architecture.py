"""Verrou d'architecture sur la famille `preset_*` — < 400 lignes/fichier, < 50 lignes/fonction.

`preset_backtest.py` avait dérivé à 793 lignes avec cinq fonctions au-dessus de 50, ce qui
bloquait toute évolution : le hook `file_guard` refusait la moindre édition du fichier, donc
le rolling universe, le câblage d'`impact.py` et les séries macro étaient tous coincés derrière
le même mur. Le découpage du 25/08 l'a ramené sous la règle ; ce test empêche la re-dérive.

Il vérifie AUSSI que la façade continue d'exposer l'API publique : les sites d'appel
(apps/api/snapshot.py, scripts, tests) importent depuis `preset_backtest`, pas depuis les
modules internes.
"""

import ast
from pathlib import Path

import pytest

PKG = Path(__file__).resolve().parents[2] / "packages" / "backtest"
MAX_LIGNES_FICHIER = 400
MAX_LIGNES_FONCTION = 50

MODULES = sorted(PKG.glob("preset_*.py"))

# Ce que les sites d'appel importent depuis `packages.backtest.preset_backtest`.
API_PUBLIQUE = [
    "preset_backtest", "preset_equity_daily", "preset_latest_weights",
    "preset_ledger", "preset_trade_log",
    "_weights_at", "_concentrate", "_price_universe",
    "EXEC_LAG_PAR_DEFAUT", "MIN_BARRES_REGIME", "ALIGNEMENT_PAR_DEFAUT",
]


def test_il_y_a_bien_des_modules_preset():
    """Garde-fou du garde-fou : si le glob ne trouve rien, les tests ci-dessous sont vides."""
    assert len(MODULES) >= 5


@pytest.mark.parametrize("mod", MODULES, ids=lambda p: p.name)
def test_fichier_sous_le_plafond(mod: Path):
    n = len(mod.read_text(encoding="utf-8").splitlines())
    assert n <= MAX_LIGNES_FICHIER, f"{mod.name} : {n} lignes > {MAX_LIGNES_FICHIER}"


@pytest.mark.parametrize("mod", MODULES, ids=lambda p: p.name)
def test_fonctions_sous_le_plafond(mod: Path):
    arbre = ast.parse(mod.read_text(encoding="utf-8"))
    trop_longues = []
    for noeud in ast.walk(arbre):
        if isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef)):
            n = (noeud.end_lineno or noeud.lineno) - noeud.lineno + 1
            if n > MAX_LIGNES_FONCTION:
                trop_longues.append(f"{noeud.name} ({n} lignes)")
    assert not trop_longues, f"{mod.name} : {', '.join(trop_longues)}"


@pytest.mark.parametrize("nom", API_PUBLIQUE)
def test_facade_expose_l_api(nom: str):
    """Le découpage ne doit casser AUCUN site d'appel existant."""
    import packages.backtest.preset_backtest as facade
    assert hasattr(facade, nom), f"`{nom}` n'est plus importable depuis preset_backtest"
