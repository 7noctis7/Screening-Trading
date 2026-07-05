"""Round-trip du journal (P0-4 Phase 2) — appariement FIFO des ventes, sans réseau.

Contrats vérifiés :
  1. vente totale → lot fermé (exit/pnl/durée), plus aucun lot ouvert ;
  2. vente partielle → scission : fraction FERMÉE (id suffixé) + lot restant réduit (même id) ;
  3. FIFO : le lot le plus ancien ferme d'abord ;
  4. pas de prix de sortie → RIEN n'est écrit (on n'invente jamais) ;
  5. MFE/MAE depuis la série OHLC entre entrée et sortie ; série absente → None ;
  6. les features de DÉCISION de l'entrée sont conservées sur l'enregistrement fermé.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from packages.core.models import AssetClass, Side, TradeRecord
from packages.execution.live_roundtrip import close_sells, mfe_mae, open_lots
from packages.storage import SqliteTradeJournal


def _journal(tmp_path):
    return SqliteTradeJournal(tmp_path / "journal.db")


def _lot(id: str, sym: str = "AAPL", qty: float = 10.0, price: float = 100.0,
         ts: datetime | None = None, venue: str = "Alpaca") -> TradeRecord:
    return TradeRecord(
        id=id, instrument=sym, asset_class=AssetClass.EQUITY, venue=venue, side=Side.LONG,
        qty=qty, entry_ts=ts or datetime(2026, 7, 1, tzinfo=timezone.utc), entry_price=price,
        avg_price=price, entry_reason="test", features_snapshot={"rank_score": 1.5})


def test_full_close_sets_exit_and_pnl(tmp_path):
    j = _journal(tmp_path)
    j.append(_lot("L1"), legacy=False)
    ts = datetime(2026, 7, 5, tzinfo=timezone.utc)
    n = close_sells(j, [{"symbol": "AAPL", "venue": "Alpaca",
                         "exit_price": 110.0, "notional": 1100.0}], ts=ts)
    assert n == 1
    assert open_lots(j) == []
    t = [x for x in j.all(legacy=False) if x.id == "L1"][0]
    assert t.exit_price == 110.0 and t.exit_ts is not None
    assert abs(t.pnl_net - 100.0) < 1e-6          # (110-100) × 10
    assert abs(t.pnl_pct - 0.10) < 1e-9
    assert t.is_win is True and t.duration_s == 4 * 86400.0
    assert t.features_snapshot == {"rank_score": 1.5}   # features de décision intactes


def test_partial_close_splits_lot(tmp_path):
    j = _journal(tmp_path)
    j.append(_lot("L1", qty=10.0), legacy=False)
    n = close_sells(j, [{"symbol": "AAPL", "venue": "Alpaca",
                         "exit_price": 100.0, "notional": 400.0}])   # vend 4 sur 10
    assert n == 1
    lots = open_lots(j)
    assert len(lots) == 1 and lots[0].id == "L1" and abs(lots[0].qty - 6.0) < 1e-9
    closed = [t for t in j.all(legacy=False) if t.exit_ts is not None]
    assert len(closed) == 1 and closed[0].id == "L1-X1" and abs(closed[0].qty - 4.0) < 1e-9


def test_fifo_oldest_lot_closes_first(tmp_path):
    j = _journal(tmp_path)
    t0 = datetime(2026, 6, 1, tzinfo=timezone.utc)
    j.append(_lot("OLD", qty=5.0, ts=t0), legacy=False)
    j.append(_lot("NEW", qty=5.0, ts=t0 + timedelta(days=10)), legacy=False)
    close_sells(j, [{"symbol": "AAPL", "venue": "Alpaca",
                     "exit_price": 100.0, "notional": 600.0}])       # 6 → OLD entier + 1 de NEW
    ids_open = [t.id for t in open_lots(j)]
    assert ids_open == ["NEW"]                     # OLD fermé en premier
    assert abs(open_lots(j)[0].qty - 4.0) < 1e-9   # NEW réduit de 1


def test_no_exit_price_writes_nothing(tmp_path):
    j = _journal(tmp_path)
    j.append(_lot("L1"), legacy=False)
    n = close_sells(j, [{"symbol": "AAPL", "venue": "Alpaca",
                         "exit_price": 0.0, "notional": 500.0}])
    assert n == 0
    assert len(open_lots(j)) == 1                  # lot intact, rien d'inventé


def test_mfe_mae_from_series_and_absent(tmp_path):
    e = datetime(2026, 7, 1, tzinfo=timezone.utc)
    x = datetime(2026, 7, 3, tzinfo=timezone.utc)
    series = [{"t": "2026-06-30", "h": 999.0, "l": 1.0},             # hors fenêtre → ignorée
              {"t": "2026-07-01", "h": 105.0, "l": 98.0},
              {"t": "2026-07-02", "h": 112.0, "l": 95.0},
              {"t": "2026-07-03", "h": 108.0, "l": 101.0}]
    fe, ae = mfe_mae(series, e, x, 100.0)
    assert abs(fe - 0.12) < 1e-9 and abs(ae - (-0.05)) < 1e-9
    assert mfe_mae(None, e, x, 100.0) == (None, None)
    assert mfe_mae([], e, x, 100.0) == (None, None)

    j = _journal(tmp_path)
    j.append(_lot("L1", ts=e), legacy=False)
    close_sells(j, [{"symbol": "AAPL", "venue": "Alpaca",
                     "exit_price": 108.0, "notional": 1080.0}],
                {"AAPL": series}, ts=x)
    t = [c for c in j.all(legacy=False) if c.exit_ts is not None][0]
    assert abs(t.mfe - 0.12) < 1e-9 and abs(t.mae - (-0.05)) < 1e-9


def test_sell_exceeding_lots_ignores_excess(tmp_path):
    j = _journal(tmp_path)
    j.append(_lot("L1", qty=2.0), legacy=False)
    n = close_sells(j, [{"symbol": "AAPL", "venue": "Alpaca",
                         "exit_price": 100.0, "notional": 10_000.0}])  # 100 > 2 détenues
    assert n == 1 and open_lots(j) == []           # ferme ce qui existe, ignore l'excédent
