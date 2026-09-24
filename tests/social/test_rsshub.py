"""`scripts/rsshub.sh` manipule une SESSION X complète. Ses gardes sont épinglées ici.

Le cookie `auth_token` n'est pas une clé d'API révocable à la carte : c'est la session
entière du compte qui l'a émis. Trois façons de le laisser fuir, trois tests :
  1. le port publié sur toutes les interfaces — le `docker-compose.yml` officiel le
     fait, et Docker contourne ufw : Internet disposerait d'un relais vers le compte ;
  2. le fichier secret lisible par d'autres utilisateurs de la machine ;
  3. le jeton passé en `-e CLE=valeur` sur la ligne de commande, que `ps` affiche à
     quiconque est connecté.

Les tests exécutent le VRAI script avec un faux `docker` sur le PATH, qui se contente
de noter ses appels : on vérifie ce que le script ferait, sans rien lancer.
"""
from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[2]
SCRIPT = RACINE / "scripts" / "rsshub.sh"


def _lancer(tmp_path: Path, secret: Path, *args: str) -> tuple[int, str, str]:
    faux = tmp_path / "bin"
    faux.mkdir(exist_ok=True)
    journal = tmp_path / "appels"
    docker = faux / "docker"
    docker.write_text(f'#!/bin/sh\necho "docker $*" >> "{journal}"\n')
    docker.chmod(0o755)
    env = {**os.environ, "PATH": f"{faux}:{os.environ['PATH']}",
           "QUANT_RSSHUB_ENV": str(secret)}
    r = subprocess.run(["bash", str(SCRIPT), *args], env=env, capture_output=True,
                       text=True, timeout=30)
    appels = journal.read_text() if journal.exists() else ""
    return r.returncode, r.stdout + r.stderr, appels


def _secret(tmp_path: Path, droits: int, contenu: str = "TWITTER_AUTH_TOKEN=abc\n"):
    s = tmp_path / "rsshub.env"
    s.write_text(contenu)
    s.chmod(droits)
    return s


def test_le_port_n_ecoute_QUE_sur_la_boucle_locale(tmp_path):
    code, _, appels = _lancer(tmp_path, _secret(tmp_path, 0o600))
    assert code == 0
    assert "-p 127.0.0.1:1200:1200" in appels
    assert "-p 1200:1200" not in appels and "0.0.0.0" not in appels


def test_le_jeton_passe_par_FICHIER_jamais_sur_la_ligne_de_commande(tmp_path):
    """`-e TWITTER_AUTH_TOKEN=…` s'afficherait dans `ps` pour tout utilisateur."""
    secret = _secret(tmp_path, 0o600, "TWITTER_AUTH_TOKEN=s3cr3t\n")
    _, _, appels = _lancer(tmp_path, secret)
    assert "--env-file" in appels
    assert "s3cr3t" not in appels


@pytest.mark.parametrize("droits", [0o644, 0o640, 0o604])
def test_un_secret_LISIBLE_par_d_autres_fait_REFUSER_le_demarrage(tmp_path, droits):
    code, sortie, appels = _lancer(tmp_path, _secret(tmp_path, droits))
    assert code != 0
    assert "Refus de démarrer" in sortie
    assert "docker run" not in appels, "le conteneur a démarré malgré un secret exposé"


def test_un_secret_ABSENT_dit_comment_le_creer_sans_rien_lancer(tmp_path):
    code, sortie, appels = _lancer(tmp_path, tmp_path / "nulle-part.env")
    assert code != 0
    assert "chmod 600" in sortie and "SECONDAIRE" in sortie
    assert "docker run" not in appels


def test_un_jeton_VIDE_n_est_pas_une_configuration(tmp_path):
    secret = _secret(tmp_path, 0o600, "TWITTER_AUTH_TOKEN=\n")
    code, _, appels = _lancer(tmp_path, secret)
    assert code != 0 and "docker run" not in appels


def test_le_risque_de_compte_est_ECRIT_dans_le_script():
    """Un script qui utilise un cookie de session sans dire lequel utiliser finit par
    être lancé avec le compte principal."""
    texte = SCRIPT.read_text(encoding="utf-8")
    assert "COMPTE SECONDAIRE, JAMAIS LE PRINCIPAL" in texte


def test_le_script_est_executable():
    assert SCRIPT.stat().st_mode & stat.S_IXUSR
