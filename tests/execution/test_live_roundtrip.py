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
    assert abs(t.pnl_gross - 100.0) < 1e-6        # (110-100) × 10, avant frais
    # La commission estimée du barème (réglementaire SEC/TAF à la vente) creuse
    # l'écart : `pnl_net` ne peut plus égaler `pnl_gross` (ADR-0131).
    assert t.pnl_net < t.pnl_gross
    assert t.fees_source == "estimated"
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


# QTY_REELLE prime sur notional/prix (05/09) — cf. `packages/research/sur_fermeture.py`.
# Sur le compte réel, OSCR a été fermé à 99,18 unités (le delta PLANIFIÉ) alors que le
# fill réel du courtier était bien plus petit : ~85 unités de « réalisé » inventées.


def test_qty_reelle_prime_sur_le_delta_planifie(tmp_path):
    """Le fill RÉEL (14) doit fermer 14, pas les 99 du delta planifié — sinon on
    invente ~85 unités de « réalisé », exactement le cas OSCR mesuré le 05/09."""
    j = _journal(tmp_path)
    j.append(_lot("L1", qty=100.0), legacy=False)
    n = close_sells(j, [{"symbol": "AAPL", "venue": "Alpaca", "exit_price": 100.0,
                         "notional": 9900.0,
                         "qty_reelle": 14.0}])   # planifié 99, fait 14
    assert n == 1
    lots = open_lots(j)
    assert len(lots) == 1 and abs(lots[0].qty - 86.0) < 1e-9   # 100 - 14, PAS 100-99
    closed = [t for t in j.all(legacy=False) if t.exit_ts is not None][0]
    assert abs(closed.qty - 14.0) < 1e-9


def test_sans_qty_reelle_le_comportement_est_inchange(tmp_path):
    """Repli : sans fill citable, `notional / prix` reste le seul calcul disponible."""
    j = _journal(tmp_path)
    j.append(_lot("L1", qty=10.0), legacy=False)
    n = close_sells(j, [{"symbol": "AAPL", "venue": "Alpaca",
                         "exit_price": 100.0, "notional": 400.0}])   # aucun qty_reelle
    assert n == 1
    assert abs(open_lots(j)[0].qty - 6.0) < 1e-9


def test_qty_reelle_nulle_ou_negative_retombe_sur_le_notional(tmp_path):
    """`qty_reelle=0` (champ absent côté prod) ne doit pas bloquer la fermeture."""
    j = _journal(tmp_path)
    j.append(_lot("L1", qty=10.0), legacy=False)
    n = close_sells(j, [{"symbol": "AAPL", "venue": "Alpaca", "exit_price": 100.0,
                         "notional": 1000.0, "qty_reelle": 0.0}])
    assert n == 1 and open_lots(j) == []


def test_le_jour_d_ENTREE_est_exclu_de_la_MFE():
    """Le cron achète une heure avant la clôture : le plus haut du jour d'entrée est
    presque toujours antérieur à l'achat. L'inclure surestime la MFE, donc sous-estime
    la capture — dans le sens exact qui fabriquerait « nos sorties rendent les gains ».

    Mesuré le 10/09 : capture d'une sortie à +1 % — 12 % avec le jour d'entrée,
    67 % sans. Un facteur 5, du même ordre que le signal cherché."""
    e = datetime(2026, 8, 3, 19, 5, tzinfo=timezone.utc)     # 15h05 ET
    x = datetime(2026, 8, 4, 19, 5, tzinfo=timezone.utc)
    serie = [{"t": "2026-08-03", "h": 108.0, "l": 99.0},     # +8 % LE MATIN, hors portée
             {"t": "2026-08-04", "h": 101.5, "l": 97.0}]
    fe, ae = mfe_mae(serie, e, x, 100.0)
    assert abs(fe - 0.015) < 1e-9, "le haut du jour d'entrée ne doit pas compter"
    assert abs(ae - (-0.03)) < 1e-9


def test_un_aller_retour_INTRADAY_rend_None():
    """Entrée et sortie le même jour : aucune barre postérieure. Une excursion intraday
    ne se mesure pas sur des barres quotidiennes — on le dit au lieu de l'inventer."""
    e = datetime(2026, 8, 3, 14, 0, tzinfo=timezone.utc)
    x = datetime(2026, 8, 3, 19, 0, tzinfo=timezone.utc)
    serie = [{"t": "2026-08-03", "h": 108.0, "l": 99.0}]
    assert mfe_mae(serie, e, x, 100.0) == (None, None)


def test_une_MFE_ne_peut_PAS_etre_negative():
    """« Maximum Favorable Excursion » ne peut pas être défavorable. Le chemin d'un
    trade commence au prix d'ENTRÉE : l'excursion favorable minimale est zéro.

    Mesuré le 10/09 sur le journal réel : BTC/USDC MFE −0,35 %, LTC/USDC −2,28 %,
    AVAX/USDC −2,30 %. Le titre avait gappé à la baisse sans jamais revenir — le plus
    haut des barres postérieures restait sous l'entrée."""
    e = datetime(2026, 8, 3, tzinfo=timezone.utc)
    x = datetime(2026, 8, 5, tzinfo=timezone.utc)
    serie = [{"t": "2026-08-04", "h": 97.0, "l": 93.0},     # jamais au-dessus de 100
             {"t": "2026-08-05", "h": 98.0, "l": 90.0}]
    fe, ae = mfe_mae(serie, e, x, 100.0)
    assert fe == 0.0, "le prix n'est jamais remonté : l'excursion favorable est nulle"
    assert abs(ae - (-0.10)) < 1e-9


def test_une_MAE_ne_peut_PAS_etre_positive():
    """Symétrique : un titre qui ne redescend jamais sous son entrée n'a pas subi
    d'excursion adverse."""
    e = datetime(2026, 8, 3, tzinfo=timezone.utc)
    x = datetime(2026, 8, 5, tzinfo=timezone.utc)
    serie = [{"t": "2026-08-04", "h": 112.0, "l": 104.0},
             {"t": "2026-08-05", "h": 115.0, "l": 108.0}]
    fe, ae = mfe_mae(serie, e, x, 100.0)
    assert abs(fe - 0.15) < 1e-9
    assert ae == 0.0


def test_les_excursions_normales_ne_sont_PAS_ecrasees():
    """Garde-fou : le bornage ne doit toucher QUE les cas contradictoires."""
    e = datetime(2026, 8, 3, tzinfo=timezone.utc)
    x = datetime(2026, 8, 5, tzinfo=timezone.utc)
    serie = [{"t": "2026-08-04", "h": 112.0, "l": 95.0}]
    fe, ae = mfe_mae(serie, e, x, 100.0)
    assert abs(fe - 0.12) < 1e-9 and abs(ae - (-0.05)) < 1e-9
