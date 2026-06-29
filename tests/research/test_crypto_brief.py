"""Tests note crypto Obsidian — déterministe, hors-ligne."""

from packages.research.crypto_brief import render


def _cockpit():
    return {
        "sentiment": {"available": True, "label": "BULLISH", "score": 68.0,
                      "drivers": ["Fear & Greed 72 (Greed)", "breadth 7/10 en hausse"]},
        "global": {"total_mcap": 2.5e12, "mcap_chg_24h": 2.1, "btc_dom": 54.2,
                   "eth_dom": 12.1},
        "fng": {"available": True, "value": 72.0, "label": "Greed"},
        "defi": {"total_tvl": 1.1e11},
        "categories": [{"name": "AI", "chg24h": 5.0}, {"name": "RWA", "chg24h": 3.0}],
        "gainers": [{"sym": "SOL", "chg24h": 9.0}],
        "losers": [{"sym": "X", "chg24h": -7.0}],
        "stablecoins": [{"sym": "USDT", "peg_dev": 0.001},
                        {"sym": "DAI", "peg_dev": -0.012}],
    }


def test_render_has_frontmatter_and_sections():
    md = render(_cockpit(), "2026-06-29")
    assert md.startswith("---\ntype: crypto_brief")
    assert "humeur: BULLISH" in md and "date: 2026-06-29" in md
    assert "## Pouls" in md and "## Narratifs" in md
    assert "$2.50 T" in md and "BTC 54.2%" in md
    # peg décroché listé (DAI -1.2%), pas l'aligné (USDT)
    assert "DAI" in md and "## ⚠ Stablecoins décrochés du peg" in md


def test_render_empty_is_nd_not_crash():
    md = render({}, "2026-06-29")
    assert "n/d" in md and "Cockpit crypto" in md
    assert "Capitalisation totale : **n/d**" in md
