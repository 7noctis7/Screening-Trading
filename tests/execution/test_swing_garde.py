"""Veto du CRO sur la sleeve swing (décision D2 du propriétaire, 01/10).

La sleeve calculait un stop et un objectif sans jamais les transmettre : une position
ouverte n'avait aucune sortie. Tant que `SORTIE_BRANCHEE` est False, le drapeau
`QUANT_SWING_PAPER` seul ne produit AUCUN ordre — ni au snapshot, ni à l'exécution.
"""

from packages.execution import swing_garde
from packages.execution import swing_sleeve as ss

SNAP = {"live": {"swing_orders": [{"symbol": "AAA", "notionnel": 1000.0}]}}


def test_le_veto_est_actif_par_defaut_et_nomme_sa_raison():
    assert swing_garde.SORTIE_BRANCHEE is False
    assert "aucune sortie" in swing_garde.veto_cro()


def test_drapeau_seul_ne_produit_aucun_ordre(monkeypatch):
    monkeypatch.setenv("QUANT_SWING_PAPER", "1")
    assert ss.swing_paper_enabled() is True          # demandé…
    assert ss.swing_paper_actif() is False           # …mais refusé par le veto
    assert ss.load_swing_orders(SNAP) == []


def test_drapeau_seul_ne_pose_aucun_ordre_au_snapshot(monkeypatch):
    monkeypatch.setenv("QUANT_SWING_PAPER", "1")
    monkeypatch.setenv("QUANT_SWING_NAV_PCT", "0.10")
    live: dict = {}
    ss.attach_swing_orders(live, bars_by_sym={"AAA": ["bar"]}, equity_nav=100_000.0,
                           ts_decision="2026-10-01T12:00:00Z")
    assert live["swing_orders"] == []


def test_veto_leve_rend_la_main_au_drapeau(monkeypatch):
    monkeypatch.setattr(swing_garde, "SORTIE_BRANCHEE", True)
    monkeypatch.setenv("QUANT_SWING_PAPER", "1")
    assert swing_garde.veto_cro() is None and ss.swing_paper_actif() is True
    assert len(ss.load_swing_orders(SNAP)) == 1


def test_un_symbole_cible_par_le_preset_quitte_la_sleeve():
    swing = [{"symbol": "AAA"}, {"symbol": "BTC/USD", "broker_symbol": "BTCUSD"}]
    targets = [{"symbol": "aaa"}, {"symbol": "QQQ"}]
    garde, retires = swing_garde.retirer_chevauchements(swing, targets,
                                                        normalize=str.upper)
    assert retires == ["AAA"] and garde == [swing[1]]
