"""Chronologie impossible — synthétique UNIQUEMENT pour valider la math."""
from datetime import UTC, datetime

from packages.core.models import AssetClass, Side, TradeRecord
from packages.research.chronologie_impossible import archive, identifier


def _trade(entry: str, exit_: str, *, exit_ts_none: bool = False) -> TradeRecord:
    return TradeRecord(
        id=f"{entry}-{exit_}", instrument="PATH", asset_class=AssetClass.EQUITY,
        venue="Alpaca", side=Side.LONG, qty=1.0,
        entry_ts=datetime.fromisoformat(entry).replace(tzinfo=UTC),
        entry_price=18.28, avg_price=18.28,
        exit_ts=(None if exit_ts_none
                 else datetime.fromisoformat(exit_).replace(tzinfo=UTC)),
        exit_price=None if exit_ts_none else 18.13, pnl_net=-19.47,
        entry_reason="", exit_reason="reconciliation-journal:abc",
    )


def test_sortie_avant_entree_est_identifiee():
    """Le vrai cas PATH : entrée 2026-09-03, sortie 2026-09-01."""
    t = _trade("2026-09-03", "2026-09-01")
    assert identifier([t]) == [t]


def test_chronologie_normale_n_est_pas_signalee():
    t = _trade("2026-08-31", "2026-09-01")
    assert identifier([t]) == []


def test_meme_jour_n_est_pas_impossible():
    """Entrée et sortie le même jour : pas d'anomalie, juste une détention courte."""
    t = _trade("2026-09-01", "2026-09-01")
    assert identifier([t]) == []


def test_lot_ouvert_est_ignore():
    t = _trade("2026-09-03", "2026-09-01", exit_ts_none=True)
    assert identifier([t]) == []


def test_archive_porte_la_preuve():
    t = _trade("2026-09-03", "2026-09-01")
    a = archive(t)
    assert a["id"] == t.id and a["entry_ts"] == str(t.entry_ts)
    assert a["exit_ts"] == str(t.exit_ts) and a["pnl_net"] == -19.47
    assert a["exit_reason"] == "reconciliation-journal:abc"
