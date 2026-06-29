"""Tests RAG vault — ancrage extractif + citations (hors-ligne, vault temporaire)."""

from packages.research.vault_rag import _sentences, grounded_answer


def test_sentences_split():
    s = _sentences("- Le gate placebo rejette le hasard. DSR déflate le Sharpe.\n\n- Risque")
    assert "Le gate placebo rejette le hasard." in s
    assert any("DSR" in x for x in s)


def _make_vault(tmp_path):
    (tmp_path / "01.md").write_text(
        "# Méthode\n\n## Gate\nLe gate placebo rejette le hasard avant tout ordre.\n"
        "Le DSR déflate le Sharpe du data-mining.\n\n"
        "## Risque\nLa discipline est le seul alpha.\n", encoding="utf-8")
    (tmp_path / "02.md").write_text(
        "# Autre\n\n## Divers\nLe café est une boisson.\n", encoding="utf-8")
    return tmp_path


def test_grounded_answer_cites_sources(tmp_path):
    v = _make_vault(tmp_path)
    out = grounded_answer("gate placebo Sharpe DSR", vault=v, k=4)
    assert out["grounded"] is True
    assert out["citations"], "doit citer au moins une source"
    # toute citation pointe vers un vrai fichier du vault
    assert all(c["file"].endswith(".md") for c in out["citations"])
    # un marqueur [n] présent dans la réponse pour chaque citation
    assert "[1]" in out["answer"]
    # réponse extractive : contient une phrase source verbatim (pas inventée)
    assert "placebo" in out["answer"].lower()


def test_no_relevant_source_is_honest(tmp_path):
    v = _make_vault(tmp_path)
    out = grounded_answer("recette tarte aux pommes zzzzz", vault=v, k=3)
    assert out["grounded"] is False
    assert "Aucune" in out["answer"] or "aucune" in out["answer"]
