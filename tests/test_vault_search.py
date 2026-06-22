from pathlib import Path

from scripts.vault_search import search


def test_search_ranks_relevant_note_first(tmp_path: Path):
    (tmp_path / "a.md").write_text(
        "# Risque\n## VaR\nValue at Risk et CVaR, EVT, GARCH pour le risque de queue.\n",
        encoding="utf-8")
    (tmp_path / "b.md").write_text(
        "# Design\n## Couleurs\nTokens UI, thème clair et sombre, typographie.\n",
        encoding="utf-8")
    hits = search("value at risk queue", tmp_path, k=2)
    assert hits, "doit retourner des résultats"
    assert hits[0]["file"] == "a.md"
    assert hits[0]["heading"] == "VaR"


def test_search_empty_vault_returns_nothing(tmp_path: Path):
    assert search("quoi que ce soit", tmp_path, k=5) == []


def test_search_indexes_code_when_requested(tmp_path: Path):
    vault = tmp_path / "vault"; vault.mkdir()
    (vault / "x.md").write_text("# Note\n## Intro\ntexte sans rapport.\n", encoding="utf-8")
    code = tmp_path / "pkg"; code.mkdir()
    (code / "risk.py").write_text(
        "def compute_value_at_risk(returns):\n    '''VaR EVT GARCH du portefeuille'''\n    return 0.0\n",
        encoding="utf-8")
    hits = search("VaR EVT GARCH portefeuille", vault, k=3, code_roots=[code])
    assert any("compute_value_at_risk" in h["heading"] for h in hits)
