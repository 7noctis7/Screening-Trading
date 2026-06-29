"""Tests fondamentaux on-chain crypto (parsers + dérivés, hors-ligne)."""

from packages.data.crypto_onchain import (
    derive,
    onchain_metrics,
    parse_coingecko,
    parse_llama_chains,
)


def test_parse_coingecko():
    data = [{"id": "bitcoin", "market_cap": 1.2e12, "total_volume": 3e10,
             "circulating_supply": 19.7e6, "max_supply": 21e6,
             "ath_change_percentage": -12.5,
             "price_change_percentage_7d_in_currency": 2.1,
             "price_change_percentage_30d_in_currency": -4.0},
            {"nope": 1}]
    out = parse_coingecko(data)
    assert "bitcoin" in out and out["bitcoin"]["mcap"] == 1.2e12
    assert out["bitcoin"]["maxs"] == 21e6


def test_parse_coingecko_total_supply_fallback():
    out = parse_coingecko([{"id": "x", "total_supply": 100, "market_cap": 10}])
    assert out["x"]["maxs"] == 100        # max_supply absent → total_supply


def test_parse_llama_chains():
    data = [{"name": "Ethereum", "tvl": 5e10}, {"name": "Solana", "tvl": 8e9},
            {"name": None, "tvl": 1}]
    out = parse_llama_chains(data)
    assert out["ethereum"] == 5e10 and out["solana"] == 8e9 and None not in out


def test_derive_metrics():
    cg = {"mcap": 1e9, "vol": 2.5e8, "circ": 50, "maxs": 100,
          "ath_chg": -30.0, "chg7d": 5.0, "chg30d": -10.0}
    d = derive(cg, tvl=4e8)
    assert d["turnover"] == 0.25 and d["float_ratio"] == 0.5
    assert d["tvl_mcap"] == 0.4 and d["dd_ath"] == -0.3 and d["mom_30d"] == -0.1


def test_derive_handles_missing():
    d = derive(None, None)
    assert d["turnover"] is None and d["tvl"] is None and d["float_ratio"] is None


def test_onchain_metrics_offline_safe():
    # sans réseau → dict des symboles, valeurs None (jamais d'exception)
    out = onchain_metrics(["BTC", "RENDER"])
    assert set(out) == {"BTC", "RENDER"} and isinstance(out["BTC"], dict)
