"""La jambe de vente a un prix de référence, ou rien — jamais 0."""

from datetime import UTC, datetime

from packages.core.models import AssetClass, Side, TradeRecord
from packages.execution.live_roundtrip import close_sells
from packages.execution.passage_ventes import close_de_decision


class _Journal:
    def __init__(self, lots):
        self.rows = list(lots)
        self.legacy = set()

    def all(self, legacy=None):
        return list(self.rows)

    def legacy_ids(self):
        return set(self.legacy)

    def append(self, trade, legacy=False):
        self.rows = [t for t in self.rows if t.id != trade.id]
        self.rows.append(trade)


def _lot():
    return TradeRecord(
        id="P-20261001-Alpaca-AAPL", instrument="AAPL",
        asset_class=AssetClass.EQUITY, venue="Alpaca", side=Side.LONG,
        qty=10, entry_ts=datetime(2026, 10, 1, tzinfo=UTC), entry_price=100.0,
        avg_price=100.0, features_snapshot={"decision_price": 99.0})


def test_la_vente_enregistre_sa_reference_et_son_shortfall():
    j = _Journal([_lot()])
    n = close_sells(j, [{"symbol": "AAPL", "venue": "Alpaca", "exit_price": 98.0,
                         "qty_reelle": 10, "decision_price": 100.0}])
    assert n == 1
    ferme = j.rows[0]
    assert ferme.features_snapshot["exit_decision_price"] == 100.0
    # Vente sous la référence : shortfall positif (défavorable).
    assert ferme.features_snapshot["exit_shortfall_bps"] == 200.0
    assert ferme.features_snapshot["decision_price"] == 99.0


def test_sans_reference_la_cle_de_sortie_n_existe_pas():
    j = _Journal([_lot()])
    close_sells(j, [{"symbol": "AAPL", "venue": "Alpaca", "exit_price": 98.0,
                     "qty_reelle": 10}])
    assert "exit_decision_price" not in (j.rows[0].features_snapshot or {})
    assert "exit_shortfall_bps" not in (j.rows[0].features_snapshot or {})


def test_la_cloture_du_jour_du_fill_n_est_pas_la_reference():
    series = [{"t": "2026-10-01", "c": 100.0}, {"t": "2026-10-02", "c": 110.0}]
    assert close_de_decision(series, "2026-10-02", None) == 100.0
    assert close_de_decision(series, "2026-10-02", 99.5) == 99.5
    assert close_de_decision([{"c": 100.0}], "2026-10-02", None) == 100.0
