"""Tests étude on-chain (parsers historiques + orchestration, hors-ligne)."""

from packages.research.onchain_study import (
    FACTORS,
    coin_series,
    parse_cg_chart,
    parse_llama_fees,
    parse_llama_hist,
    parse_llama_proto,
    run_study,
)


def test_parse_llama_fees_chart():
    chart = [[1700000000, 1.2e6], [1700086400, None], [1700172800, 1.5e6]]
    out = parse_llama_fees({"totalDataChart": chart})
    assert len(out) == 2 and 1.2e6 in out.values() and 1.5e6 in out.values()


def test_factors_registry():
    assert "tvl_mcap" in FACTORS and "fees_mcap" in FACTORS


def test_parse_cg_chart_aligns_price_and_mcap():
    data = {"prices": [[1700000000000, 100.0], [1700086400000, 102.0]],
            "market_caps": [[1700000000000, 2e9], [1700086400000, 2.04e9]]}
    out = parse_cg_chart(data)
    assert len(out) == 2
    day0 = sorted(out)[0]
    assert out[day0]["price"] == 100.0 and out[day0]["mcap"] == 2e9


def test_parse_llama_hist_unix_to_day():
    out = parse_llama_hist([{"date": 1700000000, "tvl": 5e10},
                            {"date": None, "tvl": 1}])
    assert len(out) == 1 and list(out.values())[0] == 5e10


def test_parse_llama_proto_series():
    out = parse_llama_proto({"tvl": [{"date": 1700000000, "totalLiquidityUSD": 3e8}]})
    assert list(out.values())[0] == 3e8


def test_coin_series_unknown_symbol_none():
    assert coin_series("NOTACOIN") is None


def test_run_study_offline_returns_unavailable():
    # sans réseau → pas de séries → available False (jamais d'exception)
    out = run_study(["BTC", "ETH"])
    assert out["available"] is False
