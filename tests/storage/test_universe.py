"""load_universe reste utile pour tout YAML à clé `instruments:`."""
from packages.storage import load_universe, tradable, benchmarks
from packages.core.models import AssetClass

FIX = "tests/universe/fixtures/small_universe.yaml"


def test_load_universe_instruments_key():
    u = load_universe(FIX)
    assert len(u) == 2
    assert len(tradable(u)) == 1     # AAPL
    assert len(benchmarks(u)) == 1   # ^GSPC (index)
    assert benchmarks(u)[0].asset_class is AssetClass.INDEX
