from apps.api.snapshot import _fundamentals_section


def test_section_synthetic():
    syms = ["AAPL", "MSFT", "NVDA", "JPM", "XOM"]
    acmap = {s: "equity" for s in syms}
    names = {s: s for s in syms}
    sec = {s: "Tech" for s in syms}
    r = _fundamentals_section(syms, acmap, names, sec)
    assert r["available"] and r["n"] == 5
    assert all(row["rating"] in ("BUY", "HOLD", "SELL") for row in r["rows"])
    assert all(0 <= row["score"] <= 100 for row in r["rows"])
    # trié par score décroissant
    scores = [row["score"] for row in r["rows"]]
    assert scores == sorted(scores, reverse=True)


def test_no_equities():
    r = _fundamentals_section(["BTC/USDC"], {"BTC/USDC": "crypto"}, {}, {})
    assert r["available"] is False
