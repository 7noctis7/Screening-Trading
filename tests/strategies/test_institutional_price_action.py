from datetime import UTC, datetime, timedelta

import pytest

from packages.backtest.price_action import backtest_price_action
from packages.core.models import Bar, Signal, SignalDirection
from packages.execution.costs import CostModel
from packages.strategies.institutional_price_action import (
    InstitutionalPriceAction,
    Zone,
    _first_return,
    _fvg_zones,
    confirmed_pivots,
    structure_state,
)
from packages.strategies.registry import strategies


def _bars(rows):
    start = datetime(2025, 1, 1, tzinfo=UTC)
    return [
        Bar("TEST", "1h", start + timedelta(hours=i), *row)
        for i, row in enumerate(rows)
    ]


def test_pivot_ne_backpaint_pas_avant_confirmation():
    bars = _bars(
        [
            (9, 10, 8, 9, 10),
            (9, 12, 9, 11, 10),
            (11, 11, 9, 10, 10),
        ]
    )

    assert confirmed_pivots(bars[:2], 1)[0] == []
    assert confirmed_pivots(bars, 1)[0] == [1]


def test_changement_de_direction_est_etiquete_choch(monkeypatch):
    monkeypatch.setattr(
        "packages.strategies.institutional_price_action._structure_events",
        lambda bars, span: [(4, 1), (8, -1)],
    )

    assert structure_state([], 2) == (-1, "choch")


def test_fvg_et_first_time_back_sont_deterministes():
    bars = _bars(
        [
            (9, 10, 8, 9, 10),
            (9, 11, 9, 10, 10),
            (12, 13, 12, 13, 10),
            (12, 12.5, 10.5, 11, 10),
            (11, 12, 9.5, 10, 10),
        ]
    )
    zone = _fvg_zones(bars[:3])[0]

    assert (zone.low, zone.high, zone.direction) == (10, 12, 1)
    assert _first_return(zone, bars, 3)
    assert not _first_return(zone, bars, 4)


def test_parametres_non_calibres_doivent_etre_explicites():
    assert "institutional_price_action" in strategies
    with pytest.raises(TypeError):
        InstitutionalPriceAction()  # type: ignore[call-arg]
    with pytest.raises(ValueError, match="3R"):
        InstitutionalPriceAction(2, 4, 1.5, 5, tp2_rr=2.9)


def test_gardes_publient_compteurs_et_effet_moyen():
    strategy = InstitutionalPriceAction(2, 4, 1.5, 5)

    diagnostics = strategy.guard_diagnostics()

    assert diagnostics["ftb"] == {"triggers": 0, "mean_risk_reduction": None}
    assert set(diagnostics) == {"ftb", "sfp", "volume", "rr"}


class _TwoSignals:
    name = "test"

    def generate_signals(self, bars, regime=None):
        if len(bars) not in (1, 4):
            return []
        bar = bars[-1]
        return [
            Signal(
                "TEST",
                SignalDirection.LONG,
                self.name,
                bar.ts,
                stop=99,
                target=103,
                features={"entry": 100, "risk_per_unit": 1, "tp1": 102, "tp2": 103},
            )
        ]


class _CostSignal(_TwoSignals):
    def generate_signals(self, bars, regime=None):
        signals = super().generate_signals(bars, regime)
        if signals:
            signals[0].features.update({"tp1": 103, "tp2": 104})
        return signals


def test_backtest_next_open_un_gain_un_stop_et_expected_value():
    bars = _bars(
        [
            (100, 100, 100, 100, 10),
            (100, 101, 100, 100, 10),
            (100, 104, 100, 103, 10),
            (100, 100, 100, 100, 10),
            (100, 101, 100, 100, 10),
            (100, 100, 98, 99, 10),
        ]
    )

    result = backtest_price_action(bars, _TwoSignals(), 100_000, 0.01, CostModel(0, 0))

    assert len(result.trades) == 2
    assert result.trades[0].r_multiple == pytest.approx(2.5)
    assert result.trades[1].r_multiple == pytest.approx(-1.0)
    assert result.win_rate == 0.5
    assert result.expectancy_r == pytest.approx(0.75)
    assert result.status == "UNCALIBRATED"


def test_backtest_refuse_un_risque_superieur_a_un_pourcent():
    with pytest.raises(ValueError, match="1%"):
        backtest_price_action([], _TwoSignals(), 100_000, 0.011, CostModel())


def test_stop_inclut_frais_et_slippage_dans_un_r():
    bars = _bars(
        [
            (100, 100, 100, 100, 10),
            (100, 101, 100, 100, 10),
            (100, 100, 98, 99, 10),
        ]
    )

    result = backtest_price_action(bars, _CostSignal(), 100_000, 0.01, CostModel(5, 10))

    assert result.trades[0].pnl_net == pytest.approx(-1_000)
    assert result.trades[0].r_multiple == pytest.approx(-1)


def test_gap_annule_entree_si_poche_de_liquidite_passe_sous_deux_r():
    bars = _bars(
        [
            (100, 100, 100, 100, 10),
            (101, 101, 100, 101, 10),
            (101, 104, 100, 103, 10),
        ]
    )

    result = backtest_price_action(bars, _TwoSignals(), 100_000, 0.01, CostModel(0, 0))

    assert result.trades == ()
    assert result.status == "UNCALIBRATED"


def test_zone_midpoint_est_consequent_encroachment():
    assert Zone("fvg", 1, 100, 104, 2).midpoint == 102
