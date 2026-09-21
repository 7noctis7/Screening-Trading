"""Le rapport dit-il à l'opérateur ce qu'il doit lire — sans confondre 0 et « rien » ?

Ces trois cas sont ceux qui se ressemblent à l'écran et n'ont pas du tout le même sens :
un garde-fou absent, un garde-fou à zéro, un garde-fou en panne.
"""

import importlib.util
import pathlib

import pytest

from packages.execution import garde_fous as gf

RACINE = pathlib.Path(__file__).resolve().parents[2]


@pytest.fixture
def rapport(monkeypatch):
    spec = importlib.util.spec_from_file_location("rapport_garde_fous",
                                                  RACINE / "scripts" / "garde_fous.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    monkeypatch.setattr(m, "sys", m.sys)
    return m


def _runs(gardes, mode="live"):
    return [{"horodatage": "2026-09-20T10:00:00+00:00", "mode": mode, "gardes": gardes}]


def test_un_historique_vide_dit_UNCALIBRATED_et_pourquoi(rapport, monkeypatch, capsys):
    monkeypatch.setattr(rapport, "charger", lambda: [])
    monkeypatch.setattr(rapport.sys, "argv", ["garde_fous.py"])
    rapport.main()
    out = capsys.readouterr().out
    assert "UNCALIBRATED" in out
    assert "ne dit PAS que les garde-fous n'ont rien fait" in out


def test_le_rapport_distingue_un_effet_NON_MESURABLE_d_un_effet_NUL(rapport,
                                                                    monkeypatch, capsys):
    c = gf.Collecteur()
    c.observer(gf.KILL_DD, etat=gf.ACTIVE)                       # effet non chiffrable en $
    c.observer(gf.PORTAIL, effet_usd=0.0)                        # mesuré, et nul
    monkeypatch.setattr(rapport, "charger", lambda: _runs(c.rapport()))
    monkeypatch.setattr(rapport.sys, "argv", ["garde_fous.py"])
    rapport.main()
    lignes = {x.split()[0]: x for x in capsys.readouterr().out.splitlines()
              if x.startswith("  " + gf.KILL_DD) or x.startswith("  " + gf.PORTAIL)}
    assert "n/d" in lignes[gf.KILL_DD]
    assert "0.00" in lignes[gf.PORTAIL] and "n/d" not in lignes[gf.PORTAIL]


def test_le_rapport_nomme_les_garde_fous_JAMAIS_OBSERVES(rapport, monkeypatch, capsys):
    c = gf.Collecteur()
    c.observer(gf.PORTAIL, effet_usd=0.0)
    monkeypatch.setattr(rapport, "charger", lambda: _runs(c.rapport()))
    monkeypatch.setattr(rapport.sys, "argv", ["garde_fous.py"])
    rapport.main()
    out = capsys.readouterr().out
    assert out.count("JAMAIS OBSERVÉ") >= 4          # les quatre autres garde-fous
    assert gf.DISJONCTEUR in out                     # et ils sont NOMMÉS, pas omis


def test_le_mode_par_defaut_ignore_les_apercus(rapport, monkeypatch, capsys):
    c = gf.Collecteur()
    c.observer(gf.PORTAIL, declenche=True, effet_usd=999.0, motif="poids_ligne")
    monkeypatch.setattr(rapport, "charger", lambda: _runs(c.rapport(), mode="dry"))
    monkeypatch.setattr(rapport.sys, "argv", ["garde_fous.py"])
    rapport.main()
    out = capsys.readouterr().out
    assert "0 run(s) retenu(s) sur 1 enregistré(s)" in out
    assert "999" not in out                          # un aperçu n'est pas un passage réel
