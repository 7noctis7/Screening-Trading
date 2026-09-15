"""Le garde-fou journalier est-il RÉELLEMENT dans le chemin des ordres ?

Même distinction que `test_run_live_risk_gate` : la logique est testée ailleurs
(`tests/execution/test_garde_journaliere.py`), ici on teste le CÂBLAGE. Une règle
correcte mais non branchée n'a rien empêché le 15/09.
"""

import importlib.util
import pathlib
from datetime import UTC, datetime

import pytest

RACINE = pathlib.Path(__file__).resolve().parents[2]


def _run_live():
    spec = importlib.util.spec_from_file_location("run_live", RACINE / "scripts" / "run_live.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class CourtierAvecHistorique:
    def __init__(self, ordres):
        self._ordres = ordres
        self.consulte = 0

    def orders(self, limit=100):
        self.consulte += 1
        return self._ordres


class CourtierMuet:
    """Historique illisible — le cas qui ne doit PAS bloquer la journée."""

    def orders(self, limit=100):
        raise RuntimeError("API indisponible")


def _fills(n: int, notional: float = 3000.0) -> list[dict]:
    t = datetime.now(UTC).isoformat()
    return [{"date": t, "symbol": f"S{i}", "qty": 1.0, "notional": notional}
            for i in range(n)]


def test_le_drapeau_forcer_existe(capsys):
    """Sans porte de sortie, un garde-fou qui se trompe se contourne en le retirant."""
    import sys
    m = _run_live()
    argv, sys.argv = sys.argv, ["run_live.py", "--help"]
    try:
        with pytest.raises(SystemExit):
            m._parse_args()
    finally:
        sys.argv = argv
    assert "--forcer" in capsys.readouterr().out


def test_journee_deja_jouee_detectee():
    m = _run_live()
    br = CourtierAvecHistorique(_fills(8))
    brokers = (("Alpaca", br, 100_000.0, {}), ("Bitmart", None, 0.0, {}))
    assert m._deja_rebalance_aujourdhui(brokers) is True
    assert br.consulte == 1


def test_journee_vierge_laisse_passer():
    m = _run_live()
    brokers = (("Alpaca", CourtierAvecHistorique([]), 100_000.0, {}),
               ("Bitmart", None, 0.0, {}))
    assert m._deja_rebalance_aujourdhui(brokers) is False


def test_historique_illisible_ne_bloque_pas():
    """Un garde-fou qui se déclenche sur SA PROPRE panne gèle le robot sans motif."""
    m = _run_live()
    brokers = (("Alpaca", CourtierMuet(), 100_000.0, {}), ("Bitmart", None, 0.0, {}))
    assert m._deja_rebalance_aujourdhui(brokers) is False


def test_les_deux_courtiers_sont_agreges():
    """Quatre ordres chez l'un et quatre chez l'autre font bien une journée jouée —
    compter poche par poche laisserait passer un doublon réparti."""
    m = _run_live()
    brokers = (("Alpaca", CourtierAvecHistorique(_fills(1)), 100_000.0, {}),
               ("Bitmart", CourtierAvecHistorique(_fills(1)), 10_000.0, {}))
    assert m._deja_rebalance_aujourdhui(brokers) is True


def test_courtier_absent_ignore():
    m = _run_live()
    brokers = (("Alpaca", None, 0.0, {}), ("Bitmart", None, 0.0, {}))
    assert m._deja_rebalance_aujourdhui(brokers) is False


def test_desarmement_respecte(monkeypatch):
    m = _run_live()
    monkeypatch.setenv("QUANT_REBAL_MULTI", "1")
    brokers = (("Alpaca", CourtierAvecHistorique(_fills(8)), 100_000.0, {}),
               ("Bitmart", None, 0.0, {}))
    assert m._deja_rebalance_aujourdhui(brokers) is False


def test_le_garde_est_appele_avant_reconcile():
    """Le refus doit sortir AVANT `_reconcile` : refuser après l'envoi ne refuse rien."""
    src = (RACINE / "scripts" / "run_live.py").read_text(encoding="utf-8")
    i_garde = src.index("_deja_rebalance_aujourdhui(brokers)")
    i_rec = src.index("sent, opened, sold = _reconcile(")
    assert i_garde < i_rec


def test_le_garde_ne_sarme_pas_en_dry_run():
    """Un aperçu n'envoie rien : le bloquer n'aurait aucun sens et cacherait la cible."""
    src = (RACINE / "scripts" / "run_live.py").read_text(encoding="utf-8")
    ligne = next(l for l in src.splitlines() if "_deja_rebalance_aujourdhui(brokers)" in l
                 and "def " not in l)
    assert "not dry" in ligne and "a.forcer" in ligne
