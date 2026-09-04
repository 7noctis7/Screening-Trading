"""Audit du turnover, synthétique — valide la math (mandat données réelles)."""
from datetime import UTC, datetime, timedelta

from packages.core.models import AssetClass, Side, TradeRecord
from packages.research.turnover_audit import auditer, rapport

_T0 = datetime(2026, 8, 1, tzinfo=UTC)


def _trade(i: int, duree_j: float, pnl_pct: float, mfe: float | None, *,
           motif: str = "reconciliation paper (reduce/close)",
           fees: float = 1.0) -> TradeRecord:
    entry = _T0 + timedelta(days=i)
    exit_ = entry + timedelta(days=duree_j)
    return TradeRecord(
        id=f"t{i}", instrument="QQQ", asset_class=AssetClass.EQUITY, venue="Alpaca",
        side=Side.LONG, qty=1.0, entry_ts=entry, entry_price=100.0, avg_price=100.0,
        exit_ts=exit_, exit_price=100.0 * (1 + pnl_pct), fees=fees, slippage=0.0,
        exit_reason=motif, pnl_pct=pnl_pct, is_win=pnl_pct > 0,
        duration_s=duree_j * 86400.0, mfe=mfe, mae=None,
    )


def test_journal_vide_est_uncalibrated():
    a = auditer([])
    assert a.n_trades == 0
    assert "UNCALIBRATED" in rapport(a)


def test_trades_ouverts_ignores():
    ouvert = TradeRecord(id="o1", instrument="QQQ", asset_class=AssetClass.EQUITY,
                         venue="Alpaca", side=Side.LONG, qty=1.0, entry_ts=_T0,
                         entry_price=100.0, avg_price=100.0)
    a = auditer([ouvert])
    assert a.n_trades == 0


def test_frais_et_duree_medianes():
    trades = [_trade(0, 1.0, 0.02, 0.03, fees=1.0),
              _trade(1, 3.0, -0.01, 0.005, fees=2.0)]
    a = auditer(trades)
    assert a.n_trades == 2
    assert a.frais_totaux == 3.0
    assert a.duree_mediane_j == 2.0                 # médiane de [1.0, 3.0]


def test_taux_de_gain():
    trades = [_trade(0, 1, 0.05, 0.05), _trade(1, 1, -0.02, None),
              _trade(2, 1, 0.01, 0.01)]
    a = auditer(trades)
    assert a.taux_gain == round(2 / 3, 3)


def test_capture_ignore_mfe_absent_ou_nul():
    trades = [_trade(0, 1, 0.02, 0.04), _trade(1, 1, 0.01, None),
              _trade(2, 1, -0.01, 0.0)]
    a = auditer(trades)
    assert a.n_capture_mesurable == 1                # seul le premier a un MFE > 0
    assert a.capture_mediane == 0.5                  # 0.02 / 0.04


def test_capture_basse_signale_une_sortie_prematuree():
    """Sortie loin du meilleur point observé pendant la détention → capture basse."""
    trades = [_trade(0, 5, 0.005, 0.08)]              # +8% en route, sorti à +0.5%
    a = auditer(trades)
    assert a.capture_mediane is not None and a.capture_mediane < 0.1


def test_un_seul_motif_de_sortie_est_signale():
    """État réel du système aujourd'hui : aucun TP/SL, une seule cause de clôture."""
    trades = [_trade(0, 1, 0.01, 0.02), _trade(1, 2, -0.01, None)]
    a = auditer(trades)
    assert len(a.motifs_de_sortie) == 1
    assert "AUCUNE sortie déclenchée par un TP ou un SL" in rapport(a)


def test_plusieurs_motifs_ne_declenchent_pas_l_alerte():
    trades = [_trade(0, 1, 0.01, 0.02, motif="stop"),
              _trade(1, 2, -0.01, None, motif="tp")]
    a = auditer(trades)
    assert len(a.motifs_de_sortie) == 2
    assert "AUCUNE sortie" not in rapport(a)


def test_profit_factor_rentable_malgre_taux_de_gain_bas():
    """1 gagnant sur 3, mais le gagnant compense largement les deux perdants."""
    trades = [_trade(0, 1, 0.10, 0.10), _trade(1, 1, -0.02, None),
              _trade(2, 1, -0.02, None)]
    a = auditer(trades)
    assert a.taux_gain == round(1 / 3, 3)
    assert a.profit_factor is not None and a.profit_factor > 1
    assert "rentable malgré taux bas" in rapport(a)


def test_petit_echantillon_est_signale():
    trades = [_trade(i, 1, 0.01, None) for i in range(5)]
    a = auditer(trades)
    assert "trop petit pour distinguer" in rapport(a)
