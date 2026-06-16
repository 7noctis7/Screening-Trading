from collections import Counter
from packages.data.universe import UniverseBuilder


def test_offline_build_static_only():
    res = UniverseBuilder("config/universe.yaml", allow_network=False).build()
    by = Counter(i.asset_class.value for i in res.instruments)
    # 8 sources statiques : forex20 + commo20 + indices20 + etf100 + crypto100 + cac40 + aex24 + us_megacap117
    assert len(res.instruments) == 442
    assert by["etf"] == 101 and by["crypto"] == 100
    assert by["forex"] == 20 and by["commodity"] == 20 and by["index"] == 20
    assert by["equity"] == 181  # CAC40 (40) + AEX (24) + US megacap (117)


def test_network_sources_skipped_offline():
    res = UniverseBuilder("config/universe.yaml", allow_network=False).build()
    assert "sp500" in res.skipped and "us_listings" in res.skipped


def test_dedup_by_symbol_venue():
    # construire deux fois ne change pas le total (dédoublonnage déterministe)
    a = UniverseBuilder("config/universe.yaml", allow_network=False).build()
    b = UniverseBuilder("config/universe.yaml", allow_network=False).build()
    assert len(a.instruments) == len(b.instruments)


def test_dedup_removes_cross_source_duplicates(tmp_path=None):
    import tempfile, os
    cfg = ("sources:\n"
           "  - { id: a, kind: static, file: data/seed/etf_top100.csv, enabled: true }\n"
           "  - { id: b, kind: static, file: data/seed/etf_top100.csv, enabled: true }\n")
    f = tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False)
    f.write(cfg); f.close()
    from packages.data.universe import UniverseBuilder
    r = UniverseBuilder(f.name, allow_network=False).build()
    os.unlink(f.name)
    assert r.per_source["b"] == 0           # 2e source : tout en doublon
    assert r.duplicates_removed == 101
    assert len({i.symbol for i in r.instruments}) == len(r.instruments)  # zéro doublon
