"""« Mon robot tourne-t-il ? » — le contrôle qui répondait oui sans regarder.

L'ancienne version n'interrogeait que `launchctl`. Sur Linux l'outil est absent : elle
imprimait « vérif planif ignorée » et renvoyait True. Le contrôle censé garantir que le
rebalancement est planifié validait donc TOUTE machine Linux, y compris un VPS où
`crontab -l` répond « no crontab for ubuntu ». Le symptôme dormait depuis des semaines
dans le journal — cinq décisions de sortie en soixante-trois jours — sans que rien ne le
relie à l'absence de planificateur.
"""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "verify_journal", RACINE / "scripts" / "verify_journal.py")
verif = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(verif)


class _Reponse:
    def __init__(self, sortie: str = "") -> None:
        self.stdout, self.stderr, self.returncode = sortie, "", 0


def _machine(monkeypatch, *, launchctl=None, crontab=None) -> None:
    """Simule une machine : chaîne = l'outil répond ça, None = l'outil n'existe pas."""
    def faux_run(cmd, **_kw):
        reponses = {"launchctl": launchctl, "crontab": crontab}
        sortie = reponses.get(cmd[0])
        if sortie is None:
            raise FileNotFoundError(cmd[0])
        return _Reponse(sortie)

    monkeypatch.setattr(subprocess, "run", faux_run)
    monkeypatch.setattr(verif, "LIVE_LOGS", [])


def test_un_linux_sans_crontab_echoue_au_lieu_de_passer(monkeypatch, capsys) -> None:
    """LE test. C'est l'état réel du VPS le 10/09 : `no crontab for ubuntu`."""
    _machine(monkeypatch, launchctl=None, crontab="")

    assert verif.check_schedule() is False
    assert "AUCUN rebalancement planifié" in capsys.readouterr().out


def test_un_cron_installe_passe(monkeypatch) -> None:
    """Contrôle positif : sans lui, un contrôle qui échoue toujours passerait aussi."""
    _machine(monkeypatch, launchctl=None,
             crontab="5 16 * * 1-5 /home/u/Screening-Trading/scripts/cron_live.sh")
    assert verif.check_schedule() is True


def test_un_launchagent_charge_passe(monkeypatch) -> None:
    """Le Mac reste couvert : le correctif ajoute cron, il ne retire pas launchd."""
    _machine(monkeypatch, launchctl=f"-\t0\t{verif.LAUNCHD_LABEL}", crontab=None)
    assert verif.check_schedule() is True


def test_une_machine_sans_aucun_planificateur_ne_valide_pas(monkeypatch, capsys)\
        -> None:
    """Ne pas savoir n'est pas une réussite. C'est exactement l'erreur d'origine :
    l'absence d'outil était traitée comme une absence de problème."""
    _machine(monkeypatch, launchctl=None, crontab=None)

    assert verif.check_schedule() is False
    assert "impossible d'affirmer" in capsys.readouterr().out


def test_une_sonde_distingue_outil_absent_et_rien_de_planifie(monkeypatch) -> None:
    """Les deux réponses sont opposées ; les confondre fait passer pour vérifié ce qui
    n'a pas été regardé."""
    monkeypatch.setattr(subprocess, "run",
                        lambda *_a, **_k: (_ for _ in ()).throw(FileNotFoundError()))
    assert verif._sonde(["absent"], "x") is None

    monkeypatch.setattr(subprocess, "run", lambda *_a, **_k: _Reponse("rien ici"))
    assert verif._sonde(["present"], "x") is False

    monkeypatch.setattr(subprocess, "run", lambda *_a, **_k: _Reponse("voici x ici"))
    assert verif._sonde(["present"], "x") is True


@pytest.mark.parametrize("sortie", ["", "no crontab for ubuntu"])
def test_les_formes_de_crontab_vide_sont_toutes_un_echec(monkeypatch, sortie) -> None:
    _machine(monkeypatch, launchctl=None, crontab=sortie)
    assert verif.check_schedule() is False
