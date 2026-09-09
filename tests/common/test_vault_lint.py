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


def test_un_crochet_ouvrant_isole_n_avale_pas_le_fichier(tmp_path) -> None:
    """LE défaut du 09/09, produit par le texte d'un ADR lui-même.

    Une cible de wikilink ne franchit jamais une fin de ligne. Sans cette contrainte,
    un `[[` isolé — dans un exemple, un extrait de code mal découpé — avalait tout le
    fichier jusqu'au prochain `]`, et le rapport affichait un « lien mort » de plusieurs
    paragraphes. Illisible, et faux.
    """
    from packages.common.vault_lint import extract_links

    texte = "un [[ orphelin\n\nplein de texte\n\nfin ]] et [[Vrai]] ici\n"
    wikis, _ = extract_links(texte)

    assert all("\n" not in w for w in wikis), wikis
    assert "Vrai" in wikis


def test_les_accents_graves_multiples_delimitent_aussi(tmp_path) -> None:
    """Markdown autorise N accents graves, et il en faut N pour refermer. ``  `x`  ``
    — deux accents pour CITER un accent — est le cas qui a piégé la première version :
    elle ne connaissait que le délimiteur simple, coupait au mauvais endroit et laissait
    un `[[` orphelin derrière elle."""
    from packages.common.vault_lint import extract_links, sans_code

    texte = "Le linter voyait `` [[` ]] `` comme un lien. Et [[Reel]] en est un.\n"
    assert "[[" not in sans_code(texte).split("Et")[0]

    wikis, _ = extract_links(texte)
    assert wikis == {"Reel"}, wikis


def test_le_vault_reel_ne_produit_aucun_pseudo_lien(tmp_path) -> None:
    """Contrôle sur les VRAIES notes : aucune cible ne doit contenir de saut de ligne
    ni dépasser une longueur de nom de fichier plausible."""
    from pathlib import Path

    from packages.common.vault_lint import extract_links

    racine = Path(__file__).resolve().parents[2] / "vault"
    for note in racine.rglob("*.md"):
        wikis, _ = extract_links(note.read_text(encoding="utf-8", errors="ignore"))
        for w in wikis:
            assert "\n" not in w and len(w) <= 120, f"{note.name} → {w[:80]!r}"


def test_un_adr_date_du_futur_est_signale(tmp_path) -> None:
    """L'erreur exacte du 09/09 : douze ADR datés du LENDEMAIN, et rien pour le dire.
    Un ADR enregistre une décision PRISE ; sa date ne peut pas être à venir."""
    from datetime import date

    from packages.common.vault_lint import dates_futures

    v = _vault(tmp_path)
    (v / "02_DECISIONS.md").write_text(
        "## ADR-0111 — Un titre (2026-09-10)\n\ncorps\n"
        "## ADR-0110 — Un autre (2026-09-09)\n", encoding="utf-8")

    trouves = dates_futures(v, date(2026, 9, 9))
    assert [t["date"] for t in trouves] == ["2026-09-10"], trouves
    assert "ADR-0111" in trouves[0]["entete"]

    # le lendemain, plus rien à signaler : c'est la DATE DU JOUR qui tranche
    assert dates_futures(v, date(2026, 9, 10)) == []


def test_une_seance_de_journal_datee_du_futur_est_signalee(tmp_path) -> None:
    from datetime import date

    from packages.common.vault_lint import dates_futures

    v = _vault(tmp_path)
    (v / "04_JOURNAL.md").write_text(
        "# 04 — JOURNAL\n\n## Session 2026-09-10 (8e) — demain\n"
        "## Session 2026-09-09 — aujourd'hui\n", encoding="utf-8")

    assert [t["date"] for t in dates_futures(v, date(2026, 9, 9))] == ["2026-09-10"]


def test_une_date_future_dans_le_CORPS_n_est_pas_une_erreur(tmp_path) -> None:
    """Le contrôle est volontairement ÉTROIT. « à rejuger au 2026-12-01 » dans le texte
    d'un ADR est un rendez-vous légitime : le signaler serait un faux positif permanent,
    et un avertissement permanent finit par être ignoré — y compris quand il a
    raison."""
    from datetime import date

    from packages.common.vault_lint import dates_futures

    v = _vault(tmp_path)
    (v / "02_DECISIONS.md").write_text(
        "## ADR-0111 — Un titre (2026-09-09)\n\n"
        "À rejuger au 2026-12-01, quand l'historique couvrira un choc de taux.\n",
        encoding="utf-8")

    assert dates_futures(v, date(2026, 9, 9)) == []


def test_un_entete_sans_date_n_est_pas_une_erreur(tmp_path) -> None:
    """Les ADR d'avant 0030 n'en portent pas. On ne contrôle que ce qui est écrit."""
    from datetime import date

    from packages.common.vault_lint import dates_futures

    v = _vault(tmp_path)
    (v / "02_DECISIONS.md").write_text(
        "## ADR-0029 — Long-only = scope v1 assume\n", encoding="utf-8")

    assert dates_futures(v, date(2026, 9, 9)) == []


def test_la_date_future_ferme_le_gate_de_lint_vault(tmp_path) -> None:
    """`ok` doit basculer : sans cela le contrôle existe mais ne bloque rien."""
    from datetime import date

    v = _vault(tmp_path)
    (v / "02_DECISIONS.md").write_text(
        "## ADR-0111 — Un titre (2026-09-10)\n", encoding="utf-8")

    r = lint_vault(v, date(2026, 9, 9))
    assert r["ok"] is False and len(r["dates_futures"]) == 1
    assert lint_vault(v, date(2026, 9, 10))["ok"] is True


def test_le_vault_reel_ne_porte_aucune_date_future() -> None:
    """Contrôle sur les VRAIES notes, à la date du jour."""
    from pathlib import Path

    from packages.common.vault_lint import dates_futures

    racine = Path(__file__).resolve().parents[2] / "vault"
    assert dates_futures(racine) == []
