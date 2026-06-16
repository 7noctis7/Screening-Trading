import json
from datetime import datetime, timezone
from types import SimpleNamespace
from apps.api import payloads as PL
from packages.core.models import CyclePhase, Position, RegimeState, RiskMode, Side


def test_regime_payload():
    rs = RegimeState(datetime(2024, 6, 1, tzinfo=timezone.utc), CyclePhase.EXPANSION,
                     RiskMode.RISK_ON, vix=14.0, extras={"pmi": 55.123})
    p = PL.regime_payload(rs, 0.9)
    assert p["cycle"] == "expansion" and p["exposure_multiplier"] == 0.9
    assert p["extras"]["pmi"] == 55.123


def test_composition_totals_and_pnl():
    pos = [Position("AAPL", Side.LONG, 10, 100.0), Position("MSFT", Side.LONG, 5, 200.0)]
    marks = {"AAPL": 110.0, "MSFT": 190.0}     # +100 et -50
    out = PL.composition_payload(pos, marks)
    assert out["totals"]["invested"] == 2000.0
    assert out["totals"]["pnl_abs"] == 50.0     # +100 -50
    assert out["rows"][0]["pnl_abs"] == 100.0


def test_composition_short_pnl_sign():
    pos = [Position("AAPL", Side.SHORT, 10, 100.0)]
    out = PL.composition_payload(pos, {"AAPL": 90.0})   # short gagne quand prix baisse
    assert out["rows"][0]["pnl_abs"] == 100.0


def test_benchmark_rebased_to_100():
    out = PL.benchmark_comparison([200, 220], {"SP500": [50, 55]})
    assert out["portfolio"][0] == 100.0 and out["portfolio"][1] == 110.0
    assert out["SP500"][0] == 100.0 and out["SP500"][1] == 110.0


def test_screener_payload_shape():
    ranked = [SimpleNamespace(symbol="NVDA", asset_class="equity", score=1.23,
                              contributions={"momentum": 0.8}, reason="momentum=+0.80")]
    out = PL.screener_payload(ranked, datetime(2024, 6, 1, tzinfo=timezone.utc))
    assert out["count"] == 1 and out["rows"][0]["rank"] == 1
    assert out["rows"][0]["symbol"] == "NVDA"


def test_metrics_payload_json():
    p = PL.metrics_payload([100, 101, 102, 101, 103])
    assert "sharpe" in p and json.dumps(p)   # sérialisable


def test_trade_stats_payload():
    trades = [
        SimpleNamespace(pnl_net=100.0, pnl_pct=0.10),
        SimpleNamespace(pnl_net=-50.0, pnl_pct=-0.05),
        SimpleNamespace(pnl_net=200.0, pnl_pct=0.20),
        SimpleNamespace(pnl_net=None, pnl_pct=None),   # trade ouvert : ignoré
    ]
    st = PL.trade_stats_payload(trades)
    assert st["count"] == 3 and st["wins"] == 2 and st["losses"] == 1
    assert st["pnl_total"] == 250.0
    assert st["profit_factor"] == 6.0   # 300 gains / 50 pertes
    assert st["best"] == 200.0 and st["worst"] == -50.0


def test_trade_stats_payload_empty():
    assert PL.trade_stats_payload([]) == {"count": 0}
