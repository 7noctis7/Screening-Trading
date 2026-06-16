"""Teste le parser Wikipédia OFFLINE en pointant read_html sur une fixture HTML locale."""
import pytest

from packages.data.universe import constituent_sources

# `pd.read_html` requiert un parseur HTML (lxml). Absent => skip propre, pas d'échec.
pytest.importorskip("pandas", reason="pandas requis pour read_html")
pytest.importorskip("lxml", reason="lxml requis par pandas.read_html (extra 'data')")

FIX = "tests/universe/fixtures/index_table.html"


def test_wikipedia_parses_and_applies_suffix():
    src = constituent_sources.create(
        "wikipedia", id="t", url=FIX, symbol_col="Symbol",
        suffix=".PA", venue="EPA", currency="EUR")
    inst = src.fetch()
    syms = [i.symbol for i in inst]
    assert "AAPL.PA" in syms and "MSFT.PA" in syms


def test_wikipedia_dot_to_dash():
    src = constituent_sources.create(
        "wikipedia", id="t", url=FIX, symbol_col="Symbol", dot_to_dash=True)
    syms = [i.symbol for i in src.fetch()]
    assert "BRK-B" in syms  # BRK.B -> BRK-B (format Yahoo)
