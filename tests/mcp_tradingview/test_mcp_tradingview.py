"""Tests du connecteur MCP TradingView (purs, hors-ligne)."""

import json

import pytest

from packages.mcp_tradingview import alerts as A
from packages.mcp_tradingview import server as S
from packages.mcp_tradingview.models import BlackoutZone, ChartMarker, Overlay, RiskBand
from packages.mcp_tradingview.pine import generate_pine_script
from packages.mcp_tradingview.store import OverlayStore


# ── models ────────────────────────────────────────────────────────────────
def test_marker_validation():
    ChartMarker("2026-06-18", "buy", 100.0).validate()
    with pytest.raises(ValueError):
        ChartMarker("18/06/2026", "buy").validate()        # date invalide
    with pytest.raises(ValueError):
        ChartMarker("2026-06-18", "hold").validate()       # side invalide


def test_riskband_order_and_overlay_sort():
    with pytest.raises(ValueError):
        RiskBand("2026-06-18", upper=1.0, lower=2.0).validate()   # upper < lower
    ov = Overlay("aapl", bands=[RiskBand("2026-06-18", 2, 1), RiskBand("2026-06-17", 3, 1)]).validate()
    assert ov.ticker == "AAPL"
    assert [b.time for b in ov.bands] == ["2026-06-17", "2026-06-18"]   # trié croissant


def test_blackout_validation():
    BlackoutZone("2026-06-01", "2026-06-05", "earnings").validate()
    with pytest.raises(ValueError):
        BlackoutZone("2026-06-05", "2026-06-01").validate()   # end avant start


# ── store ─────────────────────────────────────────────────────────────────
def test_store_roundtrip_atomic(tmp_path):
    st = OverlayStore(tmp_path / "ov.json")
    st.set_markers("AAPL", [ChartMarker("2026-06-18", "buy", 100.0)])
    st.set_bands("AAPL", [RiskBand("2026-06-18", 110, 90)])
    st.set_blackouts("AAPL", [BlackoutZone("2026-07-28", "2026-07-30", "Q2")])
    got = st.get("aapl")                                   # insensible à la casse
    assert got["ticker"] == "AAPL"
    assert len(got["markers"]) == 1 and len(got["bands"]) == 1 and len(got["blackouts"]) == 1
    assert json.loads((tmp_path / "ov.json").read_text())["AAPL"]["markers"][0]["side"] == "buy"
    st.clear("AAPL")
    assert st.get("AAPL")["markers"] == []


# ── pine ──────────────────────────────────────────────────────────────────
def test_pine_v5_contains_params_and_header():
    code = generate_pine_script("preset QQQ50", {"params": {"dd_target": 0.45, "band": 0.03}})
    assert code.startswith("//@version=5")
    assert "strategy(" in code and "preset QQQ50" in code
    assert "0.45" in code and "0.03" in code
    assert "ta.stdev" in code and "no-trade band" in code.lower()


def test_pine_accepts_yaml_string_and_defaults():
    code = generate_pine_script("p", "params:\n  dd_target: 0.6\n")
    # PyYAML peut être absent → on tolère défaut OU valeur lue, mais le script reste valide
    assert "//@version=5" in code and "strategy(" in code


# ── alerts → veto ─────────────────────────────────────────────────────────
def test_alerts_parse_and_veto(tmp_path):
    p = tmp_path / "al.json"
    A.append_alert({"ticker": "spy", "kind": "circuit_breaker", "severity": "critical"}, path=p)
    A.append_alert({"symbol": "qqq", "type": "trend_break", "level": "warn"}, path=p)
    got = A.fetch_tv_technical_alerts(path=p)
    assert len(got) == 2 and got[0].ticker == "SPY" and got[0].severity == "critical"
    veto = A.to_risk_veto(got)
    assert veto["veto"] is True and veto["reduce"] == 0.0 and veto["n_alerts"] == 2


def test_alerts_missing_file_is_safe(tmp_path):
    assert A.fetch_tv_technical_alerts(path=tmp_path / "nope.json") == []
    assert A.to_risk_veto([]) == {"veto": False, "reduce": 1.0, "reasons": [], "by_ticker": {}, "n_alerts": 0}


# ── server tool dispatch ──────────────────────────────────────────────────
def test_server_tools_listed():
    names = {t["name"] for t in S.list_tools()}
    assert {"plot_signal_on_chart", "overlay_risk_bands", "generate_pine_script",
            "fetch_tv_technical_alerts", "set_blackout_zones"} <= names


def test_server_call_tool_pine_and_unknown():
    res = S.call_tool("generate_pine_script", {"strategy_name": "x"})
    assert res["ok"] and res["pine"].startswith("//@version=5")
    assert "error" in S.call_tool("does_not_exist", {})


def test_var_cone_brackets_price_and_positive():
    import math
    from packages.mcp_tradingview.risk_overlays import Z_VAR95, var_cone
    times = [f"2026-01-{(i % 28) + 1:02d}" for i in range(80)]
    closes = [100 * math.exp(0.0004 * i + 0.01 * math.sin(i)) for i in range(80)]
    bands = var_cone(times, closes, z=Z_VAR95, lookback=21)
    assert len(bands) > 0
    for b in bands:
        b.validate()
        assert b.upper > b.lower >= 0.0                  # cône cohérent, plancher ≥ 0


def test_var_cone_too_short_returns_empty():
    from packages.mcp_tradingview.risk_overlays import var_cone
    assert var_cone(["2026-01-01", "2026-01-02"], [100.0, 101.0]) == []


def test_auto_risk_bands_api_down_is_graceful():
    # API injoignable → pas de crash, available=False
    res = S.call_tool("auto_risk_bands", {"ticker": "AAPL", "base_url": "http://127.0.0.1:9"})
    assert res.get("available") is False


def test_server_plot_signal_validation_error_is_caught():
    # side invalide → ValueError dans le handler → encapsulé en {"error": ...}, pas de crash
    res = S.call_tool("plot_signal_on_chart", {"ticker": "AAPL",
                                               "markers": [{"time": "2026-06-18", "side": "nope"}]})
    assert "error" in res


# ── A3 : backtest Python équivalent au Pine ────────────────────────────────
def test_pine_equiv_backtest_metrics():
    import math
    from packages.mcp_tradingview.pine import pine_equiv_backtest
    times = [f"2026-{((i//28)%12)+1:02d}-{(i%28)+1:02d}" for i in range(400)]
    closes = [100 * math.exp(0.0003 * i) * (1 + 0.02 * math.sin(i / 7)) for i in range(400)]
    m = pine_equiv_backtest(times, closes, lookback=60)
    assert m["available"] is True
    assert -1.0 <= m["max_drawdown"] <= 0.0
    assert 0.0 <= m["avg_exposure"] <= m["params"]["max_weight"] + 1e-9
    assert m["n_days"] > 0


def test_pine_equiv_backtest_too_short():
    from packages.mcp_tradingview.pine import pine_equiv_backtest
    assert pine_equiv_backtest(["2026-01-01"], [100.0])["available"] is False


# ── A2 : overlay triple-barrier ────────────────────────────────────────────
def test_triple_barrier_overlay():
    import math
    from packages.mcp_tradingview.risk_overlays import triple_barrier_overlay
    times = [f"2026-01-{(i % 28) + 1:02d}" for i in range(60)]
    closes = [100 * (1 + 0.01 * i) for i in range(60)]      # tendance haussière → TP touché
    bands, mks = triple_barrier_overlay(times, closes, entry_dates=[times[5]], pt=2.0, sl=2.0, horizon=20)
    assert len(bands) >= 1 and len(mks) == 1
    for b in bands:
        b.validate(); assert b.upper > b.lower >= 0.0
    assert mks[0].side == "sell"


def test_triple_barrier_overlay_no_entry():
    from packages.mcp_tradingview.risk_overlays import triple_barrier_overlay
    assert triple_barrier_overlay(["2026-01-01"], [100.0], entry_dates=[]) == ([], [])


# ── C : query_market_db (lecture seule) ────────────────────────────────────
def test_query_market_db_rejects_non_select():
    assert "error" in S.call_tool("query_market_db", {"db": "market", "sql": "DROP TABLE bars"})
    assert "error" in S.call_tool("query_market_db", {"db": "market", "sql": "select 1; delete from bars"})
    assert "error" in S.call_tool("query_market_db", {"db": "evil", "sql": "select 1"})


def test_compare_pine_python_api_down_graceful():
    res = S.call_tool("compare_pine_python", {"ticker": "AAPL", "base_url": "http://127.0.0.1:9"})
    assert res.get("available") is False
