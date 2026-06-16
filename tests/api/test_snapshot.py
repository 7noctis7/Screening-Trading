import json
from functools import lru_cache
from apps.api.snapshot import build_snapshot


@lru_cache(maxsize=1)
def _snap():
    return build_snapshot(seed=7)


def test_snapshot_keys_and_json():
    snap = _snap()
    assert set(snap) == {"meta", "dashboard", "screener", "portfolio", "trades",
                         "open_trades", "trade_stats", "universe", "data", "themes", "ml"}
    assert "regime" in snap["dashboard"] and "metrics" in snap["dashboard"]
    assert "benchmarks" in snap["portfolio"]
    # méta : fraîcheur + délai différé
    assert snap["meta"]["delay_minutes"] == 15 and snap["meta"]["generated_at"]
    json.dumps(snap)        # tout le snapshot est JSON-sérialisable (contrat API)


def test_snapshot_new_sections():
    snap = _snap()
    # univers COMPLET : liste exhaustive + sources + répartition par classe
    uni = snap["universe"]
    assert uni["sources_total"] >= uni["sources_enabled"] >= 1
    assert uni["instruments_total"] == len(uni["instruments"]) > 100
    assert uni["seed_total"] > 0 and uni["by_asset_class"]
    # données : collecte sur TOUT l'univers + qualité + couches DB
    data = snap["data"]
    assert data["symbols_total"] == len(data["collection"]) > 100
    assert data["total_bars"] > 0
    assert data["quality"]["ok"] is True
    assert len(data["layers"]) >= 3
    # stats de trades cohérentes
    st = snap["trade_stats"]
    assert st["count"] == st["wins"] + st["losses"]


def test_snapshot_full_universe_and_recency():
    """L'univers entier est tradé et l'historique va jusqu'à une date récente."""
    from datetime import datetime, timezone
    snap = _snap()
    meta = snap["meta"]
    assert meta["universe_size"] > 100
    assert meta["traded_assets"] > 50          # de nombreux actifs tradés (pas 5)
    # récence : dernière barre proche d'aujourd'hui (fenêtre se termine maintenant)
    last = datetime.fromisoformat(meta["last_bar"])
    assert (datetime.now(timezone.utc) - last).days <= 3
    # trades exposés couvrant de nombreux symboles distincts
    syms = {t["instrument"] for t in snap["trades"]}
    assert len(syms) > 20


def test_snapshot_dates_and_themes():
    snap = _snap()
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


def test_universe_has_us_equities_and_usdc():
    """L'univers offline inclut des actions US (PLTR cherchable) et les cryptos en USDC."""
    uni = _snap()["universe"]
    syms = {i["symbol"] for i in uni["instruments"]}
    assert "PLTR" in syms and "NVDA" in syms          # actions US présentes
    crypto = [i["symbol"] for i in uni["instruments"] if i["asset_class"] == "crypto"]
    assert crypto and all("/USDC" in s for s in crypto)   # paires en USDC, plus d'USDT
    assert not any("/USDT" in s for s in syms)


def test_positions_linked_to_sector_and_ml():
    """Chaque position porte son secteur/stance ; le ML score l'univers (cross-section)."""
    snap = _snap()
    for p in snap["dashboard"]["positions"]:
        assert "sector" in p and p["stance"] in {"bullish", "bearish", "neutral"}
    ml = snap["ml"]
    assert ml["available"] and ml["n_train"] > 1000 and ml["top_conviction"]
    # score ML propagé au screener
    assert any(r.get("ml_score") is not None for r in snap["screener"]["rows"])
