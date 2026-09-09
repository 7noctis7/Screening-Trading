"""Tests du lint de vault (structurel, hors-ligne via tmp_path)."""

from packages.common.vault_lint import extract_links, lint_vault


def test_extract_links_wiki_and_path():
    wikis, paths = extract_links(
        "voir [[02_DECISIONS]] et [[Note|alias]] et [lien](09_Events/AAPL.md)")
    assert wikis == {"02_DECISIONS", "Note"} and paths == {"09_Events/AAPL.md"}


def _vault(tmp_path):
    v = tmp_path / "vault"
    (v / "08_Alphas").mkdir(parents=True)
    return v


def test_detects_dead_link(tmp_path):
    v = _vault(tmp_path)
    (v / "00_INDEX.md").write_text("voir [[Existe]] et [[Fantome]]", encoding="utf-8")
    (v / "Existe.md").write_text("ok", encoding="utf-8")
    r = lint_vault(v)
    assert not r["ok"]
    assert any(d["link"] == "[[Fantome]]" for d in r["dead_links"])
    assert all(d["link"] != "[[Existe]]" for d in r["dead_links"])


def test_detects_orphan_in_subfolder(tmp_path):
    v = _vault(tmp_path)
    (v / "00_INDEX.md").write_text("rien", encoding="utf-8")
    (v / "08_Alphas" / "momentum.md").write_text("personne ne me lie", encoding="utf-8")
    r = lint_vault(v)
    assert "momentum.md" in r["orphans"]
    # une note référencée n'est PAS orpheline
    (v / "00_INDEX.md").write_text("[[momentum]]", encoding="utf-8")
    assert "momentum.md" not in lint_vault(v)["orphans"]


def test_detects_duplicate_adr(tmp_path):
    v = _vault(tmp_path)
    (v / "02_DECISIONS.md").write_text(
        "## ADR-0001 — a\n## ADR-0002 — b\n## ADR-0001 — doublon", encoding="utf-8")
    r = lint_vault(v)
    assert r["duplicate_adrs"] == ["0001"] and not r["ok"]


def test_clean_vault_ok(tmp_path):
    v = _vault(tmp_path)
    (v / "00_INDEX.md").write_text("[[08_Alphas/x]]", encoding="utf-8")
    (v / "08_Alphas" / "x.md").write_text("lié", encoding="utf-8")
    r = lint_vault(v)
    assert r["ok"] and r["dead_links"] == [] and r["duplicate_adrs"] == []


def test_un_lien_cite_dans_du_code_n_est_pas_un_lien(tmp_path) -> None:
    """LE faux positif du 09/09. `00_INDEX.md` documente « suivre un lien `[[...]]` » ;
    le linter y voyait deux liens morts et les comptait parmi les vrais. Deux fausses
    alertes noyées dans la liste, dans un outil dont le seul travail est de faire
    remonter les vraies."""
    from packages.common.vault_lint import lint_vault

    (tmp_path / "00_INDEX.md").write_text(
        "Pour suivre un lien `[[...]]`, faire Cmd+clic.\n\n"
        "```\nexemple : [[NoteQuiNExistePas]]\n```\n"
        "Et un VRAI lien mort : [[Fantome]]\n", encoding="utf-8")

    morts = {d["link"] for d in lint_vault(tmp_path)["dead_links"]}
    assert morts == {"[[Fantome]]"}, morts


def test_un_gabarit_ne_signale_pas_ses_espaces_reserves(tmp_path) -> None:
    """`[[paper_xxx]]` dans un gabarit attend d'être remplacé. Le signaler à chaque
    passage est un faux positif PERMANENT — et un avertissement permanent finit par
    être ignoré, y compris les jours où il a raison."""
    from packages.common.vault_lint import lint_vault

    (tmp_path / "_TEMPLATE.md").write_text("Voir [[paper_xxx]]\n", encoding="utf-8")
    (tmp_path / "note.md").write_text("Voir [[vraiment_absent]]\n", encoding="utf-8")

    morts = {d["link"] for d in lint_vault(tmp_path)["dead_links"]}
    assert morts == {"[[vraiment_absent]]"}, morts


def test_le_code_en_bloc_est_retire_avant_le_code_en_ligne(tmp_path) -> None:
    """Une portion en ligne peut vivre DANS un bloc, jamais l'inverse : retirer les
    blocs d'abord évite de couper un bloc en deux sur une paire d'accents graves."""
    from packages.common.vault_lint import sans_code

    texte = "```\nvoici `du code` et [[UnLien]]\n```\napres [[Reste]]"
    utile = sans_code(texte)
    assert "UnLien" not in utile
    assert "Reste" in utile
