"""Ontologie : résolution d'objets = pure projection du snapshot (aucune invention)."""
from packages.ontology import resolve

SNAP = {
    "screen": {"rows": [{"symbol": "NVDA", "name": "Nvidia", "sector": "Semi", "score": 2.1}]},
    "screener": {"rows": [{"symbol": "NVDA", "factors": {"momentum": 1.8}}]},
    "fundamentals": {"rows": []},
    "sentiment": {"rows": [{"symbol": "NVDA", "score": 0.6}]},
    "dashboard": {"real_positions": [{"symbol": "NVDA", "qty": 3.0, "market_value": 500.0}],
                  "regime": {"cycle": "expansion"}, "metrics": {"sharpe": 1.0},
                  "honesty": {"psr": 0.9}},
    "live": {"target_orders": [{"symbol": "NVDA", "weight_pct": 0.05, "asset_class": "equity"}]},
    "portfolio": {"analysis": {"limits": {"ok": True}}},
}


def test_instrument_360_joins_relations():
    o = resolve(SNAP, "instrument", "nvda")            # insensible à la casse
    assert o["id"] == "NVDA" and o["name"] == "Nvidia"
    r = o["relations"]
    assert r["ranking"]["factors"]["momentum"] == 1.8   # explicabilité jointe
    assert r["position"]["qty"] == 3.0                  # position réelle jointe
    assert r["target"]["weight_pct"] == 0.05
    assert r["fundamentals"] == {"available": False}    # absent → honnête, pas inventé


def test_unknown_returns_none():
    assert resolve(SNAP, "instrument", "ZZZZ") is None
    assert resolve(SNAP, "galaxie", "x") is None


def test_portfolio_object():
    p = resolve(SNAP, "portfolio", "main")
    assert p["regime"]["cycle"] == "expansion"
    assert p["relations"]["positions"][0]["symbol"] == "NVDA"
    assert p["relations"]["risk"]["ok"] is True


def test_crypto_symbol_formats_match():
    snap = {"dashboard": {"real_positions": [{"symbol": "BTCUSD", "qty": 1.0}]},
            "screen": {"rows": []}, "screener": {"rows": []},
            "fundamentals": {"rows": []}, "sentiment": {"rows": []},
            "live": {"target_orders": [{"symbol": "BTC/USD", "weight_pct": 0.02}]}}
    o = resolve(snap, "instrument", "BTC/USD")
    assert o["relations"]["position"]["qty"] == 1.0     # BTCUSD ↔ BTC/USD = même objet
