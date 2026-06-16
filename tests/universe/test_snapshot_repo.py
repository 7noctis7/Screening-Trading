from packages.core.models import AssetClass, Instrument
from packages.storage import UniverseRepository


def test_snapshot_roundtrip():
    repo = UniverseRepository(":memory:")
    insts = [Instrument("AAPL", AssetClass.EQUITY, "NASDAQ", "USD"),
             Instrument("BTC/USDT", AssetClass.CRYPTO, "binance", "USDT")]
    d = repo.save_snapshot(insts)
    back = repo.load_snapshot(d)
    assert {i.symbol for i in back} == {"AAPL", "BTC/USDT"}
    assert repo.latest_date() == d
