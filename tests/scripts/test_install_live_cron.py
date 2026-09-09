"""L'installateur de rebalancement ne marchait QUE sur une machine déjà planifiée.

`crontab -l` échoue quand aucun crontab n'existe, et `grep` sort en 1 quand il ne
sélectionne rien. Sous `set -euo pipefail`, le sous-shell mourait AVANT d'écrire la
nouvelle ligne : le script rendait 1 sans un mot, et rien n'était installé. Autrement
dit, il échouait exactement sur la machine qui en avait besoin. Constaté sur le VPS le
10/09 — « make: *** [live-cron-install] Error 1 », aucun message.

Le test fait tourner le VRAI script contre un `crontab` factice posé sur le PATH : c'est
la seule façon d'attraper une erreur de tuyauterie shell, qu'aucune relecture n'a vue en
plusieurs mois.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[2]
SCRIPT = RACINE / "scripts" / "install_live_cron.sh"

FAUX_CRONTAB = """#!/usr/bin/env bash
F="$FAUX_CRONTAB_FICHIER"
case "${1:-}" in
  -l) [ -s "$F" ] && cat "$F" || exit 1 ;;
  -)  cat > "$F" ;;
esac
"""


@pytest.fixture
def machine(tmp_path):
    """Une machine Linux dont le crontab est VIDE, comme le VPS au premier passage."""
    faux = tmp_path / "bin"
    faux.mkdir()
    (faux / "crontab").write_text(FAUX_CRONTAB, encoding="utf-8")
    (faux / "crontab").chmod(0o755)
    fichier = tmp_path / "crontab.txt"

    def lancer(*args: str) -> subprocess.CompletedProcess:
        env = {**os.environ, "PATH": f"{faux}:{os.environ['PATH']}",
               "FAUX_CRONTAB_FICHIER": str(fichier), "HOME": str(tmp_path)}
        return subprocess.run(["bash", str(SCRIPT), *args], env=env,
                              capture_output=True, text=True, timeout=60)

    return lancer, fichier


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash absent")
def test_installe_sur_une_machine_sans_crontab(machine) -> None:
    """LE test. C'est l'état du VPS : `no crontab for ubuntu`."""
    lancer, fichier = machine

    r = lancer()

    assert r.returncode == 0, f"échec silencieux :\n{r.stdout}\n{r.stderr}"
    planifie = fichier.read_text(encoding="utf-8")
    assert "cron_live.sh" in planifie, "rien n'a été planifié"
    assert "vérifié :" in r.stdout, "le script annonce sans relire ce qu'il a écrit"


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash absent")
def test_relancer_n_empile_pas_les_lignes(machine) -> None:
    """Un installateur qui duplique sa ligne à chaque passage ferait tourner le
    rebalancement plusieurs fois dans la même minute."""
    lancer, fichier = machine
    lancer()
    lancer()

    lignes = [x for x in fichier.read_text(encoding="utf-8").splitlines() if x.strip()]
    assert len(lignes) == 1, lignes


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash absent")
def test_desinstaller_retire_la_ligne(machine) -> None:
    lancer, fichier = machine
    lancer()

    r = lancer("--uninstall")

    assert r.returncode == 0
    assert "cron_live.sh" not in fichier.read_text(encoding="utf-8")


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash absent")
def test_l_heure_est_configurable(machine) -> None:
    """La séance NYSE va de 15h30 à 22h00 heure de Paris : l'heure doit pouvoir suivre
    la machine, sinon les ordres actions sont reportés tous les jours."""
    lancer, fichier = machine
    os.environ["QUANT_LIVE_HOUR"], os.environ["QUANT_LIVE_MIN"] = "20", "30"
    try:
        lancer()
    finally:
        del os.environ["QUANT_LIVE_HOUR"], os.environ["QUANT_LIVE_MIN"]

    assert fichier.read_text(encoding="utf-8").startswith("30 20 "), fichier.read_text()
