"""Une source sait seule si elle a de quoi lire — et c'est le SEUL endroit qui le sait.

La chaîne quotidienne ne doit pas remplir son journal d'échecs attendus : une source
sans canal, sans flux ou sans jeton n'a rien à tenter. La première version posait cette
question dans `scripts/cron_daily.sh`, en bash :

    if [ -n "${QUANT_TG_CANAUX:-}" ]; then ...

C'était FAUX, et muet. `.env` n'est lu qu'en Python (`packages/common/env.py`) : sous
cron, dont l'environnement est nu, la variable est vide, la garde échoue, et les trois
sources sont sautées chaque nuit sans une ligne dans le log. Une garde écrite au mauvais
étage n'assainit pas la tâche — elle l'éteint, et se fait passer pour de la propreté.

Ce que ces tests épinglent :
  1. chaque source répond elle-même, depuis ce qu'elle a réellement résolu ;
  2. Discord exige les DEUX (jeton ET salons) — une moitié de configuration est pire
     qu'aucune : elle ne rendrait que des 401 ;
  3. une source tierce qui ne déclare rien est réputée configurée, sinon elle serait
     muette sans que son auteur puisse comprendre pourquoi ;
  4. « pas configurée » n'est pas « en échec » : le code de sortie reste 0.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from packages.social.sources import charger_plugins, est_configuree, sources

RACINE = Path(__file__).resolve().parents[2]
charger_plugins()


def test_une_source_sans_cible_se_declare_non_configuree():
    assert not sources.create("telegram", canaux="").configuree
    assert not sources.create("rss", flux="").configuree
    assert not sources.create("discord", salons="").configuree


def test_une_source_avec_cible_se_declare_configuree():
    assert sources.create("telegram", canaux="crypto_eliz883").configuree
    assert sources.create("rss", flux="https://exemple.invalid/rss").configuree


def test_discord_exige_les_DEUX_jeton_ET_salon():
    """Une moitié de configuration ne rendrait que des 401, chaque nuit."""
    assert not sources.create("discord", salons="123", jeton="").configuree
    assert not sources.create("discord", salons="", jeton="secret").configuree
    assert sources.create("discord", salons="123", jeton="secret").configuree


def test_le_fichier_se_declare_sur_son_EXISTENCE(tmp_path):
    absent = tmp_path / "rien.jsonl"
    assert not sources.create("fichier", chemin=absent).configuree
    absent.write_text("", encoding="utf-8")
    assert sources.create("fichier", chemin=absent).configuree


def test_une_source_tierce_qui_ne_declare_RIEN_est_reputee_configuree():
    """La sauter par défaut la rendrait muette, sans moyen de comprendre pourquoi."""
    class Muette:
        def lire(self):
            return []

    assert est_configuree(Muette())


def test_pas_configuree_n_est_PAS_un_echec():
    """Le script sort 0 et en silence : `|| echo` du cron ne doit pas se déclencher."""
    r = subprocess.run(
        [sys.executable, "scripts/social_x_ingest.py", "--source", "discord",
         "--si-configuree"],
        cwd=RACINE, capture_output=True, text=True, timeout=60,
        env={"PATH": "/usr/bin:/bin", "QUANT_DISCORD_SALONS": "", "HOME": "/tmp"})
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "", r.stdout


def test_le_script_d_ingestion_LIT_le_fichier_env(monkeypatch):
    """`.env` est la seule configuration que l'utilisateur écrit à la main.

    Sans ce chargement, le script ne marchait que depuis un shell où les variables
    avaient été exportées — donc pas sous cron, et pas après un redémarrage. Le défaut
    n'aurait rien affiché : la source se serait simplement déclarée non configurée.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "ingest_sous_test", RACINE / "scripts" / "social_x_ingest.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    appels: list[int] = []
    monkeypatch.setattr(mod, "load_env", lambda: appels.append(1))
    monkeypatch.setattr(sys, "argv", ["x", "--source", "discord", "--si-configuree"])
    assert mod.main() == 0
    assert appels, ("le script n'a pas chargé `.env` — il ne marcherait que dans "
                    "un shell préparé à la main")
