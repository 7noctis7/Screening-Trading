"""CHANGELOG généré et banc de vitesse : la mécanique, pas les chiffres."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts import changelog
from scripts.bench_moteur import MOTEURS, charge, chronometrer


def test_squash_et_merge_classique_donnent_le_titre_et_le_numero(monkeypatch):
    brut = ("2026-10-31\x1fCI : mypy bloquant (#455)\x1f\x1e"
            "2026-10-29\x1fMerge pull request #453 from x/feat\x1fFeat/vector rag\n\x1e"
            "2026-10-01\x1fchore: keepalive mensuel\x1f\x1e"
            "2026-09-30\x1fcommit direct sans PR\x1f\x1e")
    monkeypatch.setattr(changelog, "_git", lambda *a: brut)
    assert changelog.entrees("main") == [("2026-10-31", "CI : mypy bloquant", 455),
                                         ("2026-10-29", "Feat/vector rag", 453)]


def test_le_rendu_groupe_par_mois_dans_l_ordre_de_l_historique():
    texte = changelog.rendre([("2026-10-31", "B", 2), ("2026-09-30", "A", 1)], "0.1.0",
                             "2026-10-31")
    assert "## [0.1.0] — 2026-10-31" in texte
    assert texte.index("### 2026-10") < texte.index("### 2026-09")
    assert "- B (#2)" in texte and "- A (#1)" in texte


def test_le_banc_mesure_les_deux_moteurs_sur_une_charge_seedee():
    data = charge(2, 1)
    assert data.keys() == charge(2, 1).keys() and len(data["S000"]) > 200
    for fn in MOTEURS.values():
        assert chronometrer(fn, data, 1) > 0
