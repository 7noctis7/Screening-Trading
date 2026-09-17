"""`make sync` ne doit plus détruire en silence un fichier non commité.

CE QUI S'EST PASSÉ (17/09). `make verrou-regen` a régénéré `constraints.txt` sur le
VPS : 159 paquets épinglés au lieu de 81, scikit-learn et lightgbm enfin figés. Le
fichier n'a pas été commité le soir même. Le lendemain, `make sync` — dont la recette
fait `git reset --hard origin/<branche>` — l'a effacé sans un mot, et c'est `make
verrou`,
deux commandes plus loin, qui a annoncé « Verrou : 81 paquet(s) épinglé(s) ». Le travail
n'avait pas échoué : il n'existait plus, et la seule trace était un chiffre qui semblait
avoir régressé tout seul.

CE QUE CES TESTS TIENNENT. `sync` met de côté (`git stash`) AVANT de réécrire
l'arbre, en le disant ; les fichiers que la chaîne régénère elle-même restent exclus,
sinon l'avertissement deviendrait quotidien donc invisible ; et si la mise de côté
échoue, la synchronisation s'interrompt plutôt que de détruire.

Le troisième test ne lit pas la recette : il l'EXÉCUTE dans un dépôt git jetable.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[1]
MAKEFILE = RACINE / "Makefile"


def _recette(cible: str) -> list[str]:
    """Les lignes d'une cible Make, continuations jointes, commentaires ôtés.

    Une recette s'arrête à la première ligne SANS tabulation — pas à la première ligne
    vide : découper autrement déborde sur la cible suivante.
    """
    texte = MAKEFILE.read_text(encoding="utf-8").replace("\\\n", " ")
    apres = texte.split(f"\n{cible}:", 1)[1].splitlines()[1:]
    lignes = []
    for ligne in apres:
        if not ligne.startswith("\t"):
            break
        nu = ligne.strip()
        if not nu.startswith("@#"):
            lignes.append(nu)
    return lignes


def test_la_liste_des_fichiers_regeneres_est_LA_MEME_des_deux_cotes():
    """Elle est redite en dur dans le Makefile pour que `sync` ne dépende d'aucun
    interpréteur — c'est la cible qu'on lance quand l'environnement est cassé. Le prix
    de cette duplication, c'est ce test : deux listes qui divergent stasheraient un
    fichier de données tous les jours, jusqu'à ce que plus personne ne lise le message.
    """
    from packages.mlops.manifest import DONNEES_REGENEREES

    texte = MAKEFILE.read_text(encoding="utf-8")
    ligne = re.search(r"^FICHIERS_REGENERES \?= (.+)$", texte, re.M)
    assert ligne, "le Makefile doit déclarer FICHIERS_REGENERES"
    assert tuple(ligne.group(1).split()) == tuple(DONNEES_REGENEREES)


def test_la_mise_de_cote_precede_la_destruction():
    """Un garde-fou posé APRÈS `reset --hard` ne garde plus rien."""
    lignes = _recette("sync")
    garde = [i for i, x in enumerate(lignes) if "sync-garde" in x]
    dur = [i for i, x in enumerate(lignes) if "reset --hard" in x]
    assert garde and dur, lignes
    assert min(garde) < min(dur), "sync-garde doit tourner AVANT le reset --hard"


def test_sync_garde_ne_depend_d_aucun_interpreteur():
    """`sync` sert à réparer une machine en panne : elle ne peut pas exiger le venv."""
    recette = " ".join(_recette("sync-garde"))
    assert "$(PYTHON)" not in recette and "python" not in recette


def test_verrou_regen_reclame_le_commit():
    """Régénérer sans commiter produit un fichier que le prochain sync efface."""
    recette = " ".join(_recette("verrou-regen"))
    assert "git add constraints.txt" in recette
    assert "commit" in recette


@pytest.mark.skipif(not shutil.which("make") or not shutil.which("git"),
                    reason="make ou git absent")
def test_sur_un_VRAI_depot_le_fichier_non_commite_survit(tmp_path: Path):
    """La preuve par l'exécution : on modifie deux fichiers, on lance la cible, et on
    regarde ce qui reste récupérable. Lire la recette ne dirait pas si elle marche."""
    def git(*a: str) -> str:
        r = subprocess.run(["git", "-C", str(tmp_path), *a], capture_output=True,
                           text=True, check=True)
        return r.stdout

    (tmp_path / "config").mkdir()
    git("init", "-q", ".")
    git("config", "user.email", "t@t")
    git("config", "user.name", "t")
    shutil.copy(MAKEFILE, tmp_path / "Makefile")
    (tmp_path / "constraints.txt").write_text("81 paquets\n")
    (tmp_path / "config/mobile_universe.csv").write_text("hier\n")
    git("add", "-A")
    git("commit", "-qm", "base")

    (tmp_path / "constraints.txt").write_text("159 paquets\n")          # à sauver
    (tmp_path / "config/mobile_universe.csv").write_text("aujourd'hui\n")  # régénéré

    fait = subprocess.run(["make", "sync-garde"], cwd=tmp_path, capture_output=True,
                          text=True)
    assert fait.returncode == 0, fait.stderr
    assert "constraints.txt" in fait.stdout, "la cible doit NOMMER ce qu'elle écarte"

    # Le fichier régénéré n'a pas été touché : sinon l'avertissement serait quotidien.
    assert (tmp_path / "config/mobile_universe.csv").read_text() == "aujourd'hui\n"
    assert git("stash", "list").strip(), "rien n'a été mis de côté"

    # Ce qu'un `reset --hard` aurait détruit est intégralement récupérable.
    git("reset", "--hard", "-q", "HEAD")
    git("stash", "pop", "-q")
    assert (tmp_path / "constraints.txt").read_text() == "159 paquets\n"
