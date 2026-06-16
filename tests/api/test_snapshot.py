import json
from apps.api.snapshot import build_snapshot


def test_snapshot_keys_and_json():
    snap = build_snapshot(seed=7)
    assert set(snap) == {"meta", "dashboard", "screener", "portfolio", "trades",
                         "open_trades", "trade_stats", "universe", "data", "themes"}
    assert "regime" in snap["dashboard"] and "metrics" in snap["dashboard"]
    assert "benchmarks" in snap["portfolio"]
    # méta : fraîcheur + délai différé
    assert snap["meta"]["delay_minutes"] == 15 and snap["meta"]["generated_at"]
    json.dumps(snap)        # tout le snapshot est JSON-sérialisable (contrat API)


def test_snapshot_new_sections():
    snap = build_snapshot(seed=7)
    # univers COMPLET : liste exhaustive + sources + répartition par classe
    uni = snap["universe"]
    assert uni["sources_total"] >= uni["sources_enabled"] >= 1
    assert uni["instruments_total"] == len(uni["instruments"]) > 100
    assert uni["seed_total"] > 0 and uni["by_asset_class"]
    # données : collecte + qualité + couches DB
    data = snap["data"]
    assert len(data["collection"]) == 5 and data["total_bars"] > 0
    assert data["quality"]["ok"] is True
    assert len(data["layers"]) >= 3
    # stats de trades cohérentes
    st = snap["trade_stats"]
    assert st["count"] == st["wins"] + st["losses"]


def test_snapshot_dates_and_themes():
    snap = build_snapshot(seed=7)
    # axe temporel aligné sur la courbe d'equity
    dates = snap["dashboard"]["dates"]
    assert len(dates) == len(snap["dashboard"]["equity"]) > 0
    assert dates[0] < dates[-1]                       # croissant (ISO comparable)
    # thèmes : secteurs triés par YTD décroissant + setups
    th = snap["themes"]
    assert len(th["sectors"]) >= 5
    ytds = [s["ytd"] for s in th["sectors"]]
    assert ytds == sorted(ytds, reverse=True)
    assert all(s["stance"] in {"bullish", "bearish", "neutral"} for s in th["sectors"])
    assert all(s["top_assets"] for s in th["sectors"])
