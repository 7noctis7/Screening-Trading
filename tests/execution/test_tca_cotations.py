"""Coût réel par ordre : spread, dérive avant envoi, shortfall d'exécution.

Journalisation seulement : rien ici ne change un ordre. Une cotation illisible vaut
« absente », jamais zéro ; une écriture ratée ne lève pas."""

import importlib.util
import pathlib

import pytest

from packages.execution import cotations as cot
from packages.execution import tca_journal as tca

RACINE = pathlib.Path(__file__).resolve().parents[2]


def test_cotation_incoherente_ecartee_pas_corrigee():
    assert cot.valider(10.0, 9.0) is None                 # ask < bid
    assert cot.valider(0.0, 10.0) is None
    assert cot.valider("x", 10.0) is None
    q = cot.valider(99.0, 101.0, "2026-10-06T14:00:00Z")
    assert q["mid"] == 100.0 and q["spread_bps"] == pytest.approx(200.0)


def test_cotations_ne_levent_jamais():
    def panne(syms):
        raise ConnectionError("données muettes")
    assert cot.cotations(["AAPL"], lecteur=panne) == {}
    lu = cot.cotations(["AAPL", "XYZ", "BAD"], lecteur=lambda s: {
        "AAPL": (189.9, 190.1, ""), "BAD": (5.0, 4.0, "")})
    assert set(lu) == {"AAPL"} and lu["AAPL"]["mid"] == pytest.approx(190.0)


def _ordre(cote="buy"):
    return {"order_id": "o1", "venue": "Alpaca", "broker_symbol": "AAPL", "cote": cote}


def test_decomposition_achat():
    arr = cot.valider(100.9, 101.1)                       # mid 101
    li = tca.ligne(_ordre(), prix_fill=101.2, qty=10, close_decision=100.0,
                   arrivee=arr, apres=None, jour="2026-10-06")
    assert li["derive_bps"] == pytest.approx(100.0)        # +1 % de gap avant envoi
    assert li["shortfall_bps"] == pytest.approx((101.2 / 101 - 1) * 1e4)
    assert li["total_bps"] == pytest.approx(120.0)
    somme = li["derive_bps"] + li["shortfall_bps"]
    assert somme == pytest.approx(li["total_bps"], rel=0.01)
    assert li["bench_quality"] == "quote"


def test_une_vente_moins_chere_que_le_mid_est_un_cout_positif():
    li = tca.ligne(_ordre("sell"), prix_fill=99.8, qty=5, close_decision=100.0,
                   arrivee=cot.valider(99.9, 100.1), apres=None, jour="j")
    assert li["shortfall_bps"] == pytest.approx(20.0)
    assert li["total_bps"] == pytest.approx(20.0)


def test_sans_cotation_aucun_zero_invente():
    li = tca.ligne(_ordre(), prix_fill=101.0, qty=1, close_decision=100.0,
                   arrivee=None, apres=None, jour="j")
    assert li["bench_quality"] == "missing"
    assert li["spread_bps"] is None and li["shortfall_bps"] is None
    assert li["total_bps"] == pytest.approx(100.0)


def test_enregistrer_idempotent_et_resume(tmp_path):
    db = tmp_path / "journal.db"
    li = tca.ligne(_ordre(), prix_fill=101.0, qty=1, close_decision=100.0,
                   arrivee=cot.valider(100.9, 101.1), apres=None, jour="j")
    assert tca.enregistrer([li], db) == 1 and tca.enregistrer([li], db) == 1
    assert len(tca.lire(db)) == 1
    assert tca.resume(tca.lire(db))["status"] == "UNCALIBRATED"
    lignes = [{**li, "order_id": f"o{i}"} for i in range(25)]
    tca.enregistrer(lignes, db)
    r = tca.resume(tca.lire(db))
    assert r["available"] and r["spread_bps_mediane"] == pytest.approx(li["spread_bps"])


def test_enregistrer_en_panne_ne_leve_pas(tmp_path):
    li = tca.ligne(_ordre(), prix_fill=1.0, qty=1, close_decision=None, arrivee=None,
                   apres=None, jour="j")
    (tmp_path / "bloque").write_text("fichier, pas dossier")
    assert tca.enregistrer([li], tmp_path / "bloque" / "journal.db") == 0


def _run_live():
    spec = importlib.util.spec_from_file_location("run_live",
                                                  RACINE / "scripts" / "run_live.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class _Alpaca:
    def orders(self, limit=200):
        return [{"id": "o1", "symbol": "AAPL", "side": "buy", "qty": 2.0,
                 "price": 101.0},
                {"id": "o2", "symbol": "MSFT", "side": "sell", "qty": 1.0,
                 "price": 0.0}]


def test_run_live_journalise_les_ordres_remplis_seulement(monkeypatch):
    rl = _run_live()
    ecrit = {}
    monkeypatch.setattr(tca, "enregistrer", lambda lignes: ecrit.setdefault("l", lignes)
                        and len(lignes))
    monkeypatch.setattr(cot, "cotations", lambda syms, lecteur=None: {})
    snap = {"dashboard": {"chart_series": {"AAPL": [{"c": 100.0}]}}}
    opened = [{"symbol": "AAPL", "venue": "Alpaca", "broker_symbol": "AAPL",
               "order_id": "o1"}]
    sold = [{"symbol": "MSFT", "venue": "Alpaca", "broker_symbol": "MSFT",
             "order_id": "o2"},                                  # prix 0 : pas rempli
            {"symbol": "BTC/USD", "venue": "Bitmart", "broker_symbol": "BTCUSDT",
             "order_id": "o3"}]                                  # hors Alpaca
    rl._journal_tca(snap, opened, sold, _Alpaca(), {"AAPL": cot.valider(100.9, 101.1)})
    (li,) = ecrit["l"]
    assert li["order_id"] == "o1" and li["close_decision"] == 100.0
    assert li["bench_quality"] == "quote"


def test_run_live_aucune_cotation_en_apercu():
    rl = _run_live()
    assert rl._cotations_arrivee([{"symbol": "AAPL"}], {}, object(), dry=True) == {}


def test_la_mesure_est_appelee_avant_l_envoi_et_apres_les_fills():
    src = (RACINE / "scripts" / "run_live.py").read_text(encoding="utf-8")
    i_cot = src.index("cot_arrivee = _cotations_arrivee(")
    i_rec = src.index("sent, opened, sold = _reconcile(targets, brokers")
    i_fill = src.index("_attendre_les_fills(opened, sold, alpaca, bitmart)\n"
                       "        _journal_tca")
    assert i_cot < i_rec < i_fill


def test_lire_ne_cree_pas_de_base_vide(tmp_path):
    absent = tmp_path / "journal.db"
    assert tca.lire(absent) == [] and not absent.exists()


def test_symboles_crypto_des_positions_alpaca_reconnus():
    assert cot._paire_crypto("BTC/USD") == "BTC/USD"
    assert cot._paire_crypto("BTCUSD") == "BTC/USD"          # forme des positions
    assert cot._paire_crypto("AAPL") is None
    assert cot._paire_crypto("ZZZUSD") is None               # base non Alpaca


class _Q:
    bid_price, ask_price, timestamp = 99.0, 101.0, None


def test_un_lot_en_panne_ne_prive_pas_l_autre_et_deux_formes_crypto():
    def panne(x):
        raise ValueError("symbole inconnu")
    assert cot._lire_lot(panne, {"AAPL": ["AAPL"]}) == {}
    lu = cot._lire_lot(lambda x: {"BTC/USD": _Q()}, {"BTC/USD": ["BTC/USD", "BTCUSD"]})
    assert set(lu) == {"BTC/USD", "BTCUSD"} and lu["BTCUSD"][:2] == (99.0, 101.0)
