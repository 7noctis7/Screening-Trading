"""Timing signal → exécution du moteur event-driven (sprint de justesse du 02/10).

Le signal se lit au CLOSE de `t` ; l'ordre part à l'OUVERTURE de `t+1`. L'ancien moteur
remplissait au close de la barre même qui avait produit le signal — un prix qu'il venait
d'observer. Un stop traversé par un gap se remplit à l'ouverture, pas au niveau du stop.
"""

from datetime import UTC, datetime, timedelta

import pytest

from packages.backtest import BacktestEngine
from packages.core.models import Bar, Signal, SignalDirection
from packages.execution import CostModel, SimBroker
from packages.risk import RiskEngine

T0 = datetime(2026, 1, 5, tzinfo=UTC)


def _barres(ohlc: list[tuple[float, float, float, float]]) -> list[Bar]:
    return [Bar("AAA", "1d", T0 + timedelta(days=i), o, h, low, c, 1_000.0)
            for i, (o, h, low, c) in enumerate(ohlc)]


class AchatUneFois:
    """LONG à la barre `i`, avec un stop optionnel."""

    name = "test"

    def __init__(self, i: int, stop: float | None = None) -> None:
        self.i, self.stop = i, stop

    def generate_signals(self, window, regime):
        if len(window) - 1 == self.i:
            return [Signal("AAA", SignalDirection.LONG, self.name, window[-1].ts,
                           stop=self.stop, reason="entree")]
        return []


class DixTitres:
    def size(self, sig, equity, price, regime):
        return 10.0


def _run(strat, barres, exec_lag=1):
    broker = SimBroker(cash=100_000, costs=CostModel(fee_bps=0.0, slippage_bps=0.0))
    eng = BacktestEngine(strat, DixTitres(), RiskEngine([]), broker, exec_lag=exec_lag)
    return eng.run({"AAA": barres}), broker


BARRES = _barres([(100, 101, 99, 100), (110, 112, 108, 111), (111, 113, 110, 112),
                  (112, 114, 111, 113)])


def test_le_signal_du_close_t_s_execute_a_l_ouverture_t_plus_1():
    res, _ = _run(AchatUneFois(0), BARRES)
    (trade,) = res.journal.all()
    assert trade.entry_price == pytest.approx(110.0)       # open de la barre 1
    assert trade.entry_ts == BARRES[1].ts


def test_exec_lag_0_reproduit_l_ancien_remplissage_au_close():
    res, _ = _run(AchatUneFois(0), BARRES, exec_lag=0)
    (trade,) = res.journal.all()
    assert trade.entry_price == pytest.approx(100.0)       # close de la barre du signal


def test_un_stop_traverse_par_un_gap_se_remplit_a_l_ouverture():
    barres = _barres([(100, 101, 99, 100), (100, 101, 99, 100), (90, 92, 88, 91),
                      (91, 92, 90, 91)])
    res, _ = _run(AchatUneFois(0, stop=95.0), barres)
    (trade,) = res.journal.all()
    assert trade.exit_reason == "stop_hit"
    assert trade.exit_price == pytest.approx(90.0)          # l'ouverture, pas 95
    assert trade.r_multiple == pytest.approx(-2.0)          # pire que −1 : le gap


def test_un_signal_sur_la_derniere_barre_ne_s_execute_pas():
    res, broker = _run(AchatUneFois(len(BARRES) - 1), BARRES)
    assert res.journal.all() == [] and broker.equity() == pytest.approx(100_000)


def test_exec_lag_invalide_refuse():
    with pytest.raises(ValueError):
        BacktestEngine(AchatUneFois(0), DixTitres(), RiskEngine([]),
                       SimBroker(cash=1.0), exec_lag=2)
