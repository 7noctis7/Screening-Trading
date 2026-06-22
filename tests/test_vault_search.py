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
