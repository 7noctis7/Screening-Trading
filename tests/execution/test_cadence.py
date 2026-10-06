"""Cadence : la production rebalance au rythme de la règle MESURÉE, jamais au détriment
d'une réduction de risque. Le rejeu et run_live partagent la même constante."""

import importlib.util
import pathlib
from datetime import date

import pytest

from packages.execution import cadence as cad
from packages.execution import garde_fous as gf

RACINE = pathlib.Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def _sans_env(monkeypatch):
    monkeypatch.delenv(cad.ENV, raising=False)


def _ordres(jour: str, n: int = 3, notionnel: float = 1000.0) -> list[dict]:
    return [{"date": f"{jour}T15:30:00Z", "qty": 1.0, "notional": notionnel}] * n


def test_le_rejeu_et_la_production_partagent_la_cadence():
    from packages.backtest.preset_rejeu import PAS_DEFAUT
    assert PAS_DEFAUT == cad.CADENCE_DEFAUT == cad.cadence() == 5


def test_avant_l_echeance_on_ne_trade_pas():
    d = cad.evaluer(_ordres("2026-10-05"), date(2026, 10, 7))      # lundi → mercredi
    assert d["passer"] is False and d["seances"] == 2 and d["dernier"] == "2026-10-05"


def test_a_l_echeance_on_trade():
    assert cad.evaluer(_ordres("2026-10-05"), date(2026, 10, 12))["passer"] is True


def test_une_reduction_de_risque_n_attend_jamais():
    d = cad.evaluer(_ordres("2026-10-05"), date(2026, 10, 6), reduction=0.5)
    assert d["passer"] is True and d["motif"] == "réduction de risque"


def test_pas_d_historique_on_trade_et_poussiere_ignoree():
    assert cad.evaluer([], date(2026, 10, 6))["passer"] is True
    assert cad.dernier_passage(_ordres("2026-10-05", n=1)) is None         # ordre isolé
    poussiere = _ordres("2026-10-05", notionnel=1.0)
    assert cad.dernier_passage(poussiere) is None                           # poussière


def test_quotidien_retabli_par_variable(monkeypatch):
    monkeypatch.setenv(cad.ENV, "1")
    assert cad.evaluer(_ordres("2026-10-05"), date(2026, 10, 6))["passer"] is True
    monkeypatch.setenv(cad.ENV, "abc")
    assert cad.cadence() == cad.CADENCE_DEFAUT


def _run_live():
    spec = importlib.util.spec_from_file_location("run_live",
                                                  RACINE / "scripts" / "run_live.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class _Br:
    def __init__(self, ordres=None, panne=False):
        self._o, self._panne = ordres or [], panne

    def orders(self, limit=200):
        if self._panne:
            raise ConnectionError("API muette")
        return self._o


def test_run_live_compte_le_passage_refuse(monkeypatch):
    rl, obs = _run_live(), gf.Collecteur()
    monkeypatch.setattr(cad, "evaluer", lambda f, j, reduction=1.0: {
        "passer": False, "motif": "avant l'échéance", "seances": 2, "dernier": "x",
        "cadence": 5})
    assert rl._hors_cadence((("Alpaca", _Br(), 0.0, {}),), 1.0, obs) is True
    r = obs.rapport()[gf.CADENCE]
    assert r["declenchements"] == 1 and r["motifs"] == {"avant l'échéance": 1}


def test_run_live_historique_illisible_laisse_passer_et_le_dit():
    rl, obs = _run_live(), gf.Collecteur()
    assert rl._hors_cadence((("Alpaca", _Br(panne=True), 0.0, {}),), 1.0, obs) is False
    assert obs.rapport()[gf.CADENCE]["etat"] == gf.UNCALIBRATED


def test_run_live_appelle_la_cadence_apres_la_garde_journaliere():
    src = (RACINE / "scripts" / "run_live.py").read_text(encoding="utf-8")
    i, j = src.index("_deja_rebalance_aujourdhui(brokers, obs)"), \
        src.index("_hors_cadence(brokers, reduce, obs)")
    assert i < j and "not a.forcer and _hors_cadence" in src
