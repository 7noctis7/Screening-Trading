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
