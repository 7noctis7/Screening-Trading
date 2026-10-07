"""`dire()` = `print()` à l'identique + une ligne JSON ; jamais d'exception."""

from packages.common import journal_passage as jp


def test_dire_imprime_comme_print_et_journalise(tmp_path, capsys):
    chemin = jp.ouvrir(tmp_path, run="r1")
    try:
        jp.dire("  ⚠️  report", 3, "ordres")
        jp.dire("ok")
        jp.evenement("reglage", nom="QUANT_X", critique=False)
    finally:
        jp.fermer()
    assert capsys.readouterr().out == "  ⚠️  report 3 ordres\nok\n"
    lignes = jp.lire(chemin)
    assert [x["type"] for x in lignes] == ["message", "message", "reglage"]
    assert lignes[0]["niveau"] == "alerte" and lignes[1]["niveau"] == "info"
    assert {x["run"] for x in lignes} == {"r1"}
    assert lignes[0]["msg"] == "⚠️  report 3 ordres"


def test_sans_journal_ouvert_rien_n_est_ecrit(tmp_path, capsys):
    jp.fermer()
    jp.dire("seul l'écran")
    jp.evenement("x")
    assert capsys.readouterr().out == "seul l'écran\n"
    assert not list(tmp_path.iterdir())


def test_disque_inaccessible_ne_leve_pas(tmp_path):
    bloque = tmp_path / "fichier"
    bloque.write_text("pas un dossier")
    assert jp.ouvrir(bloque / "sous") is None
    jp.dire("continue")                       # aucun journal, aucune exception


def test_sous_pytest_le_journal_par_defaut_n_est_pas_ouvert():
    assert jp.ouvrir() is None


def test_run_live_n_appelle_plus_print():
    import re
    from pathlib import Path
    src = (Path(__file__).resolve().parents[2] / "scripts" / "run_live.py").read_text(
        encoding="utf-8")
    assert not re.findall(r"(?<![\w.])print\(", src)
