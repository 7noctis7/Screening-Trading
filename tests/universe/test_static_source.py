from packages.core.models import AssetClass
from packages.data.universe import constituent_sources


def test_static_reads_seed():
    src = constituent_sources.create("static", id="forex",
                                     file="data/seed/forex_top20.csv")
    inst = src.fetch()
    assert len(inst) == 20
    assert all(i.asset_class is AssetClass.FOREX for i in inst)
    assert inst[0].symbol == "EUR/USD"
    assert src.requires_network is False


def test_etf_seed_has_100():
    src = constituent_sources.create("static", id="etf",
                                     file="data/seed/etf_top100.csv")
    assert len(src.fetch()) >= 100
