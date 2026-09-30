"""Journal des ordres : l'écart décision → fill est ÉCRIT, et une vente partielle ne
duplique aucun coût.

Deux dettes mesurées dans le code le 30/09 :
  1. la colonne `slippage` n'était JAMAIS remplie, alors que le prix de décision est figé
     dans `features_snapshot` à chaque ouverture. Seul `make slippage` le recalculait ;
  2. une vente partielle recopiait les frais d'entrée ENTIERS du lot sur la tranche vendue,
     tout en les laissant sur le lot restant : la commission d'entrée était comptée deux
     fois (invisible à 0 $ chez Alpaca, réel à 25 pb chez BitMart).

Convention unique (`fills.shortfall_bps`) : positif = défavorable. Le slippage reste
DESCRIPTIF : il est déjà dans le prix de fill, on ne le retranche jamais du P&L.
"""

from __future__ import annotations

import importlib
from datetime import UTC, datetime

import pytest

from packages.core.models import AssetClass, Side, TradeRecord
from packages.execution.live_journal import agreger_achats, build_open
from packages.execution.live_roundtrip import close_sells, open_lots
from packages.storage import SqliteTradeJournal

TS = datetime(2026, 9, 30, 15, tzinfo=UTC)


def _ouvrir(fill, feats=None, sym="QQQ", classe="equity", order_id="A1"):
    return build_open(sym, venue="Alpaca", asset_class=classe, fill=fill,
                      features=feats if feats is not None else {"decision_price": 100.0},
                      ts=TS, order_id=order_id)


# ------------------------------------------------------------------ 1. écart décision → fill

def test_achat_plus_cher_que_la_decision_est_un_ecart_defavorable():
    tr = _ouvrir({"avg_price": 101.0, "qty": 3.0, "origine": "ordre", "ids": ["A1"]})
    assert tr.slippage == pytest.approx(3.0)            # (101 − 100) × 3, positif = coût


def test_achat_moins_cher_est_un_ecart_favorable():
    tr = _ouvrir({"avg_price": 99.5, "qty": 2.0, "origine": "ordre", "ids": ["A1"]})
    assert tr.slippage == pytest.approx(-1.0)


def test_une_position_de_repli_ne_mesure_rien():
    """Le prix moyen d'une POSITION mêle les achats d'autres jours : l'opposer au prix de
    décision du jour ne mesure pas l'exécution. Inconnu → None, jamais 0."""
    tr = _ouvrir({"avg_price": 101.0, "qty": 3.0, "origine": "position"})
    assert tr.slippage is None


@pytest.mark.parametrize("feats", [{}, {"decision_price": 0.0}, {"decision_price": -5.0}])
def test_sans_prix_de_decision_rien_n_est_invente(feats):
    tr = _ouvrir({"avg_price": 101.0, "qty": 3.0, "origine": "ordre", "ids": ["A1"]},
                 feats=feats)
    assert tr.slippage is None


def test_fill_sans_origine_reste_inconnu():
    assert _ouvrir({"avg_price": 101.0, "qty": 3.0}).slippage is None


def test_les_fills_du_jour_portent_leur_origine_et_leurs_ordres():
    ordres = [{"id": "A1", "symbol": "QQQ", "side": "buy", "qty": 2, "price": 100.0,
               "date": "2026-09-30T15:00:00Z"},
              {"id": "M2", "symbol": "QQQ", "side": "buy", "qty": 1, "price": 103.0,
               "date": "2026-09-30T16:00:00Z"}]
    fill = agreger_achats(ordres, "2026-09-30")["QQQ"]
    assert fill["origine"] == "ordre" and fill["ids"] == ["A1", "M2"]


@pytest.mark.parametrize("ids, order_id", [
    (["A1", "M2"], "A1"),        # le VWAP mêle l'ordre du robot et un achat manuel
    (["M2"], "A1"),              # le seul fill du jour n'est pas l'ordre envoyé
    ([""], "A1"),                # ordre du courtier sans identifiant : invérifiable
    (["A1"], None),              # identité de l'ordre envoyé inconnue
])
def test_l_ecart_n_est_attribue_qu_au_fill_de_l_ordre_envoye(ids, order_id):
    fill = {"avg_price": 101.0, "qty": 3.0, "origine": "ordre", "ids": ids}
    assert _ouvrir(fill, order_id=order_id).slippage is None


def test_le_repli_position_porte_son_origine():
    run_live = importlib.import_module("scripts.run_live")

    class _Br:
        def positions_detailed(self):
            return [{"symbol": "QQQ", "avg_price": 100.0, "qty": 3.0}]

    repli = run_live._positions_repli((("Alpaca", _Br()),))
    assert repli[("Alpaca", "QQQ")]["origine"] == "position"


# ------------------------------------------------------------------ 2. vente partielle

def _lot(qty=10.0, fees=2.5, slippage=1.0):
    return TradeRecord(
        id="P-L1", instrument="BTC/USDC", asset_class=AssetClass.CRYPTO, venue="Bitmart",
        side=Side.LONG, qty=qty, entry_ts=datetime(2026, 9, 1, tzinfo=UTC),
        entry_price=100.0, avg_price=100.0, entry_reason="test", fees=fees,
        fees_source="estimated", slippage=slippage, features_snapshot={"x": 1.0})


def test_vente_partielle_repartit_frais_et_ecart_d_entree(tmp_path):
    from packages.execution.costs import broker_charge
    j = SqliteTradeJournal(tmp_path / "j.db")
    j.append(_lot(), legacy=False)
    close_sells(j, [{"symbol": "BTC/USDC", "venue": "Bitmart", "exit_price": 110.0,
                     "notional": 440.0}], ts=TS)                 # vend 4 sur 10
    ferme = next(t for t in j.all(legacy=False) if t.exit_ts is not None)
    reste = open_lots(j)[0]
    vente = broker_charge("crypto", 110.0 * 4, side="SELL")
    assert ferme.fees == pytest.approx(2.5 * 0.4 + vente)        # 40 % de l'entrée
    assert reste.fees == pytest.approx(2.5 * 0.6)                # 60 % restent au lot
    assert ferme.slippage == pytest.approx(0.4)
    assert reste.slippage == pytest.approx(0.6)
    assert ferme.pnl_net == pytest.approx(ferme.pnl_gross - ferme.fees)


def test_vente_totale_garde_tout_le_cout(tmp_path):
    j = SqliteTradeJournal(tmp_path / "j.db")
    j.append(_lot(), legacy=False)
    close_sells(j, [{"symbol": "BTC/USDC", "venue": "Bitmart", "exit_price": 110.0,
                     "notional": 1100.0}], ts=TS)
    ferme = next(t for t in j.all(legacy=False) if t.exit_ts is not None)
    assert ferme.slippage == pytest.approx(1.0)
    assert ferme.fees > 2.5


def test_couts_inconnus_restent_inconnus_a_la_scission(tmp_path):
    j = SqliteTradeJournal(tmp_path / "j.db")
    j.append(_lot(fees=None, slippage=None), legacy=False)
    close_sells(j, [{"symbol": "BTC/USDC", "venue": "Bitmart", "exit_price": 110.0,
                     "notional": 440.0}], ts=TS)
    assert open_lots(j)[0].fees is None and open_lots(j)[0].slippage is None
