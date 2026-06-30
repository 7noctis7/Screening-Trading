"""Tests cockpit crypto — parsers purs (hors-ligne)."""

from packages.data.crypto_market import (
    accumulation_score,
    altseason,
    cockpit,
    halving,
    market_sentiment,
    movers,
    parse_categories,
    parse_chains,
    parse_fng,
    parse_global,
    parse_markets,
    parse_stablecoins,
    parse_trending,
)


def test_parse_global():
    g = parse_global({"data": {"total_market_cap": {"usd": 2.5e12},
                               "market_cap_percentage": {"btc": 54.2, "eth": 12.1},
                               "market_cap_change_percentage_24h_usd": -1.8}})
    assert g["total_mcap"] == 2.5e12 and g["btc_dom"] == 54.2
    assert g["mcap_chg_24h"] == -1.8


def test_parse_markets_and_movers():
    data = [
        {"id": "bitcoin", "symbol": "btc", "name": "Bitcoin", "current_price": 60000,
         "price_change_percentage_24h": 1.2, "market_cap": 1.2e12,
         "sparkline_in_7d": {"price": [1, 2, 3]}},
        {"id": "x", "symbol": "x", "name": "X", "current_price": 1,
         "price_change_percentage_24h": -9.0, "market_cap": 1e8},
    ]
    m = parse_markets(data)
    assert m[0]["sym"] == "BTC" and m[0]["spark7d"] == [1.0, 2.0, 3.0]
    mv = movers(m, n=1)
    assert mv["gainers"][0]["sym"] == "BTC" and mv["losers"][0]["sym"] == "X"


def test_parse_categories_sorted_desc():
    out = parse_categories([{"id": "ai", "name": "AI", "market_cap_change_24h": 2.0},
                            {"id": "rwa", "name": "RWA", "market_cap_change_24h": 5.0},
                            {"bad": 1}])
    assert [c["name"] for c in out] == ["RWA", "AI"]
    assert out[0]["id"] == "rwa"          # id propagé pour le lien CoinGecko


def test_parse_trending():
    out = parse_trending({"coins": [{"item": {"id": "foo", "name": "Foo",
                                              "symbol": "foo"}}]})
    assert out[0]["name"] == "Foo" and out[0]["sym"] == "FOO"
    assert out[0]["id"] == "foo"          # id propagé pour le lien CoinGecko


def test_parse_chains_dominance():
    c = parse_chains([{"name": "Ethereum", "tvl": 60}, {"name": "Solana", "tvl": 40}])
    assert c["total_tvl"] == 100 and c["top"][0]["chain"] == "Ethereum"
    assert c["top"][0]["dom"] == 0.6


def test_parse_stablecoins_peg_dev():
    s = parse_stablecoins({"peggedAssets": [
        {"symbol": "USDT", "circulating": {"peggedUSD": 1e11}, "price": 1.002},
        {"symbol": "DAI", "circulating": {"peggedUSD": 5e9}, "price": 0.991}]})
    assert s[0]["sym"] == "USDT" and s[0]["peg_dev"] == 0.002
    assert s[1]["peg_dev"] == -0.009
    assert s[0]["kind"] == "peg" and s[1]["kind"] == "peg"


def test_parse_stablecoins_yield_token_not_depeg():
    # USYC ~1,13 $ = token à rendement (NAV), pas un dépeg → kind="yield"
    s = parse_stablecoins({"peggedAssets": [
        {"symbol": "USYC", "circulating": {"peggedUSD": 3e9}, "price": 1.1295}]})
    assert s[0]["kind"] == "yield"


def test_parse_fng():
    assert parse_fng({"data": [{"value": "72", "value_classification": "Greed"}]}) == {
        "available": True, "value": 72.0, "label": "Greed"}
    assert parse_fng({})["available"] is False


def test_altseason_proxy():
    # BTC +0% sur 7j ; 2 alts montent, 1 baisse → 2/3 battent BTC (besoin ≥10 → top élargi)
    mk = [{"sym": "BTC", "mcap": 1e12, "spark7d": [100, 100]}]
    for i in range(12):
        up = i % 3 != 0
        mk.append({"sym": f"A{i}", "mcap": 1e9 - i,
                   "spark7d": [100, 110 if up else 90]})
    out = altseason(mk)
    assert out["available"] and 0 <= out["pct"] <= 100 and out["n"] >= 10
    assert out["label"] in ("Altseason", "Bitcoin", "Mixte")


def test_altseason_unavailable_without_btc():
    assert altseason([{"sym": "X", "mcap": 1, "spark7d": [1, 2]}])["available"] is False


def test_accumulation_score():
    # peur extrême + funding négatif + grosse part stable → score haut (accumulation)
    acc = accumulation_score({
        "fng": {"available": True, "value": 10.0},
        "derivatives": {"sentiment": {"available": True, "avg": -0.0006}},
        "global": {"total_mcap": 1e12},
        "stablecoins": [{"mcap": 1.5e11}]})
    assert acc["available"] and acc["score"] >= 60 and "ACCUMULATION" in acc["label"]
    # avidité + funding positif → score bas (euphorie)
    eu = accumulation_score({
        "fng": {"available": True, "value": 90.0},
        "derivatives": {"sentiment": {"available": True, "avg": 0.0008}},
        "global": {"total_mcap": 1e12}, "stablecoins": [{"mcap": 1e10}]})
    assert eu["score"] <= 40 and "EUPHORIE" in eu["label"]
    assert accumulation_score({})["available"] is False


def test_halving_countdown():
    h = halving(840_500)            # juste après le halving de 2024 (bloc 840 000)
    assert h["available"] and h["halving_block"] == 1_050_000
    assert h["blocks_left"] == 209_500 and h["number"] == 5
    assert h["days_left"] > 0 and 0 <= h["progress"] <= 1
    assert halving(0)["available"] is False


def test_market_sentiment_rules():
    bull = market_sentiment({
        "fng": {"available": True, "value": 80.0, "label": "Greed"},
        "global": {"mcap_chg_24h": 3.0},
        "gainers": [{"chg24h": 5}, {"chg24h": 2}], "losers": [{"chg24h": -1}]})
    assert bull["label"] == "BULLISH" and bull["score"] >= 60
    bear = market_sentiment({
        "fng": {"available": True, "value": 15.0, "label": "Fear"},
        "global": {"mcap_chg_24h": -4.0},
        "gainers": [{"chg24h": 1}], "losers": [{"chg24h": -3}, {"chg24h": -2}]})
    assert bear["label"] == "BEARISH" and bear["score"] <= 40
    assert market_sentiment({})["available"] is False


def test_cockpit_offline_safe(monkeypatch, tmp_path):
    monkeypatch.setenv("QUANT_HTTP_RETRIES", "1")    # pas de retry/backoff hors-ligne
    monkeypatch.setenv("QUANT_HTTP_BACKOFF", "0")
    monkeypatch.setenv("QUANT_CACHE_DIR", str(tmp_path))   # cache isolé/vide
    c = cockpit()                       # hors-ligne → structures vides, sans exception
    assert set(c) >= {"global", "top", "gainers", "fng", "stablecoins", "defi"}
    assert "sentiment" in c
