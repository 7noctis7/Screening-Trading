"""Audit du turnover, synthétique — valide la math (mandat données réelles)."""
from datetime import UTC, datetime, timedelta

from packages.core.models import AssetClass, Side, TradeRecord
from packages.research.turnover_audit import auditer, rapport

_T0 = datetime(2026, 8, 1, tzinfo=UTC)


def _trade(i: int, duree_j: float, pnl_pct: float, mfe: float | None, *,
           motif: str = "reconciliation paper (reduce/close)",
           fees: float = 1.0, tid: str | None = None,
           qty: float = 1.0) -> TradeRecord:
    entry = _T0 + timedelta(days=i)
    exit_ = entry + timedelta(days=duree_j)
    return TradeRecord(
        id=tid or f"t{i}", instrument="QQQ", asset_class=AssetClass.EQUITY,
        venue="Alpaca", side=Side.LONG, qty=qty, entry_ts=entry, entry_price=100.0,
        avg_price=100.0, exit_ts=exit_, exit_price=100.0 * (1 + pnl_pct), fees=fees,
        slippage=0.0, exit_reason=motif, pnl_pct=pnl_pct, is_win=pnl_pct > 0,
        duration_s=duree_j * 86400.0, mfe=mfe, mae=None,
    )


def test_journal_vide_est_uncalibrated():
    a = auditer([])
    assert a.n_positions == 0
    assert "UNCALIBRATED" in rapport(a)


def test_trades_ouverts_ignores():
    ouvert = TradeRecord(id="o1", instrument="QQQ", asset_class=AssetClass.EQUITY,
                         venue="Alpaca", side=Side.LONG, qty=1.0, entry_ts=_T0,
                         entry_price=100.0, avg_price=100.0)
    assert auditer([ouvert]).n_positions == 0


def test_frais_et_duree_medianes():
    trades = [_trade(0, 1.0, 0.02, 0.03, fees=1.0),
              _trade(1, 3.0, -0.01, 0.005, fees=2.0)]
    a = auditer(trades)
    assert a.n_positions == 2
    assert a.frais_totaux == 3.0
    assert a.duree_mediane_j == 2.0                 # médiane de [1.0, 3.0]


def test_taux_de_gain():
    trades = [_trade(0, 1, 0.05, 0.05), _trade(1, 1, -0.02, None),
              _trade(2, 1, 0.01, 0.01)]
    assert auditer(trades).taux_gain == round(2 / 3, 3)


# ── piège n°1 : une vente en plusieurs fois n'est PAS plusieurs trades ──

def test_tranches_du_meme_lot_comptent_pour_une_position():
    """Vrai journal : un lot crypto soldé en 6 fois revenait 6 fois avec son +40 %."""
    tranches = [_trade(0, 50, 0.40, None, tid=f"lot1-X{n}") for n in range(1, 7)]
    a = auditer(tranches)
    assert a.n_fermetures == 6
    assert a.n_positions == 1
    assert a.rendement_moyen_pct == 0.40           # une seule fois, pas six
    assert "une vente en plusieurs fois est UNE position" in rapport(a)


def test_tstat_calcule_sur_les_positions_pas_les_tranches():
    """|t| croît en racine de n : compter les tranches fabrique la significativité."""
    tranches = [_trade(0, 10, 0.30, None, tid=f"gagnant-X{n}") for n in range(1, 13)]
    perdants = [_trade(i, 10, -0.05, None, tid=f"perdant{i}") for i in range(1, 4)]
    a = auditer(tranches + perdants)
    assert a.n_fermetures == 15 and a.n_positions == 4
    assert a.rendement_tstat is not None and abs(a.rendement_tstat) < 2.0
    assert a.rendement_significatif is False


def test_rendement_de_position_pondere_par_la_quantite():
    a = auditer([_trade(0, 5, 0.10, None, tid="lot9-X1", qty=3.0),
                 _trade(0, 5, 0.02, None, tid="lot9-X2", qty=1.0)])
    assert a.n_positions == 1
    assert a.rendement_moyen_pct == 0.08           # (0.10*3 + 0.02*1) / 4


# ── piège n°2 : les fermetures reconstruites après coup ──

def test_fermetures_administratives_sont_signalees():
    trades = [_trade(0, 1, 0.01, None, motif="reconciliation-journal:abc-123"),
              _trade(1, 1, 0.02, None)]
    a = auditer(trades)
    assert a.n_administratives == 1
    assert "script de réconciliation" in rapport(a)


def test_motifs_administratifs_ne_masquent_pas_l_absence_de_tp_sl():
    """28 uuid de réconciliation ne doivent pas faire croire à des sorties variées."""
    trades = [_trade(i, 1, 0.01, None, motif=f"reconciliation-journal:{i}")
              for i in range(5)] + [_trade(9, 1, 0.01, None)]
    assert "aucune sortie déclenchée par un TP ou un SL" in rapport(auditer(trades))


# ── capture, profit factor, significativité ──

def test_capture_negative_signale_un_gagnant_devenu_perdant():
    """Le vrai journal : +1,9 % de MFE puis sortie à −1,0 %."""
    a = auditer([_trade(0, 2, -0.0103, 0.0192)])
    assert a.capture_mediane is not None and a.capture_mediane < 0
    assert "NÉGATIVE" in rapport(a)


def test_capture_ignore_mfe_absent_ou_nul():
    trades = [_trade(0, 1, 0.02, 0.04), _trade(1, 1, 0.01, None),
              _trade(2, 1, -0.01, 0.0)]
    a = auditer(trades)
    assert a.n_capture_mesurable == 1
    assert a.capture_mediane == 0.5                  # 0.02 / 0.04


def test_profit_factor_et_taux_de_gain_sont_separes():
    trades = [_trade(0, 1, 0.10, None), _trade(1, 1, -0.02, None),
              _trade(2, 1, -0.02, None)]
    a = auditer(trades)
    assert a.taux_gain == round(1 / 3, 3)
    assert a.profit_factor is not None and a.profit_factor > 1


def test_petit_echantillon_est_signale():
    a = auditer([_trade(i, 1, 0.01, None) for i in range(5)])
    assert "trop petit pour distinguer" in rapport(a)


def test_taux_de_gain_porte_son_biais():
    assert "perdants encore OUVERTS" in rapport(auditer([_trade(0, 1, 0.01, None)]))


def test_rendement_negatif_et_stable_est_significatif():
    trades = [_trade(i, 1, -0.01 + (0.0002 if i % 2 else -0.0002), None)
              for i in range(40)]
    a = auditer(trades)
    assert a.rendement_moyen_pct is not None and a.rendement_moyen_pct < 0
    assert a.rendement_significatif is True


def test_rendement_negatif_mais_bruite_n_est_pas_significatif():
    """Même moyenne négative, peu de positions, forte dispersion → pas distinguable."""
    trades = [_trade(0, 1, -0.02, None), _trade(1, 1, 0.05, None),
              _trade(2, 1, -0.06, None)]
    a = auditer(trades)
    assert a.rendement_tstat is not None and abs(a.rendement_tstat) < 2.0
    assert "NON significatif" in rapport(a)
