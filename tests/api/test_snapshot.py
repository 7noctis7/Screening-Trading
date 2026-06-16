import json
from apps.api.snapshot import build_snapshot


def test_snapshot_keys_and_json():
    snap = build_snapshot(seed=7)
    assert set(snap) == {"dashboard", "screener", "portfolio", "trades"}
    assert "regime" in snap["dashboard"] and "metrics" in snap["dashboard"]
    assert "benchmarks" in snap["portfolio"]
    json.dumps(snap)        # tout le snapshot est JSON-sérialisable (contrat API)
