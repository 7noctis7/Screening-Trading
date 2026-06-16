import json
from apps.api.snapshot import build_snapshot


def test_snapshot_keys_and_json():
    snap = build_snapshot(seed=7)
    assert set(snap) == {"dashboard", "screener", "portfolio", "trades",
                         "open_trades", "trade_stats", "universe", "data"}
    assert "regime" in snap["dashboard"] and "metrics" in snap["dashboard"]
    assert "benchmarks" in snap["portfolio"]
    json.dumps(snap)        # tout le snapshot est JSON-sérialisable (contrat API)


def test_snapshot_new_sections():
    snap = build_snapshot(seed=7)
    # univers : sources + seeds + répartition par classe
    uni = snap["universe"]
    assert uni["sources_total"] >= uni["sources_enabled"] >= 1
    assert uni["seed_total"] > 0 and uni["by_asset_class"]
    # données : collecte + qualité + couches DB
    data = snap["data"]
    assert len(data["collection"]) == 5 and data["total_bars"] > 0
    assert data["quality"]["ok"] is True
    assert len(data["layers"]) >= 3
    # stats de trades cohérentes
    st = snap["trade_stats"]
    assert st["count"] == st["wins"] + st["losses"]
