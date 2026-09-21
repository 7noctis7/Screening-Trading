"""Le VPS doit déployer la branche publiée, pas une branche de travail oubliée.

Régression constatée le 21/09 : ``make up`` disait « à jour » à juste titre, mais sur
``claude/screening-trading-platform-me9p11`` (build 58ab486), tandis que les livraisons
récentes étaient sur ``main``. La vérification du hash du front ne pouvait pas le voir :
le front et HEAD étaient cohérents, simplement tous deux anciens.
"""

from pathlib import Path
import re


RACINE = Path(__file__).resolve().parents[2]
MAKEFILE = RACINE / "Makefile"


def test_la_branche_de_deploiement_par_defaut_est_main():
    texte = MAKEFILE.read_text(encoding="utf-8")
    match = re.search(r"^BRANCHE\s*\?=\s*(\S+)\s*$", texte, re.MULTILINE)
    assert match, "le choix de branche doit rester explicite et testable"
    assert match.group(1) == "main"


def test_une_branche_temporaire_reste_surchargeable():
    texte = MAKEFILE.read_text(encoding="utf-8")
    assert "origin/$(BRANCHE)" in texte
    assert "git fetch origin $(BRANCHE)" in texte
