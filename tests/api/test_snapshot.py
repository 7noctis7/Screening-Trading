import json
from functools import lru_cache
from apps.api.snapshot import build_snapshot


@lru_cache(maxsize=1)
def _snap():
    return build_snapshot(seed=7)


def test_snapshot_keys_and_json():
    snap = _snap()
    assert set(snap) == {"meta", "dashboard", "screener", "portfolio", "trades",
                         "open_trades", "trade_stats", "universe", "data", "themes", "ml",
                         "sentiment", "fundamentals", "investors", "conviction", "live",
                         "preset_trades", "index_core_curves", "preset_ledger"}
    # cœur(s) indiciel(s) + satellite : bloc présent sur le dashboard
    ic = snap["dashboard"]["index_core"]
    assert "core_pct" in ic and "enabled" in ic and "symbol" in ic
    assert snap["meta"]["initial_capital"] == 10_000
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
    """L'univers inclut des actions US (PLTR cherchable) et des cryptos en USD (jamais USDT)."""
    uni = _snap()["universe"]
    syms = {i["symbol"] for i in uni["instruments"]}
    assert "PLTR" in syms and "NVDA" in syms          # actions US présentes
    crypto = [i["symbol"] for i in uni["instruments"] if i["asset_class"] == "crypto"]
    # cotées en USD : seed offline (/USDC) OU univers réel yfinance (-USD) — jamais USDT.
    assert crypto and all(("/USDC" in s) or s.endswith("-USD") for s in crypto)
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


def test_vix_playbook_and_live():
    snap = _snap()
    d = snap["dashboard"]
    assert d["vix"] > 0 and d["vix_playbook"]["regime"] in {"calme", "normal", "tendu", "panique"}
    assert d["vix_playbook"]["exposure"] in {1.2, 1.0, 0.6, 0.3}
    live = snap["live"]
    assert {b["name"] for b in live["brokers"]} == {"Alpaca", "Bitmart"}
    assert live["mode"] == "paper"
    # « non connecté » garanti UNIQUEMENT sans clés (CI). Si des clés sont présentes (machine
    # configurée), l'état dépend du broker/réseau → on n'assert pas.
    import os as _os
    if not (_os.environ.get("ALPACA_API_KEY") or _os.environ.get("BITMART_API_KEY")):
        assert live["connected"] is False
    # projection Monte-Carlo : bandes de percentiles ordonnées
    mp = snap["portfolio"]["analysis"]["mc_projection"]
    assert mp["final_p5"] <= mp["final_p50"] <= mp["final_p95"]


def test_portfolio_benchmarks_present():
    """Le portefeuille (allocation de production) est rebasé et comparé aux benchmarks."""
    b = _snap()["portfolio"]["benchmarks"]
    assert b.get("portfolio") and b["portfolio"][-1] > 0          # série présente et positive
    assert "Univers (équipondéré)" in b                           # comparaison dispo


def test_portfolio_analysis_coherent_with_production():
    """COHÉRENCE : l'analyse (corrélation) porte sur l'ALLOCATION DE PRODUCTION (preset + cœur),
    pas sur le swing legacy → corrélation ⊆ allocation preset affichée en page Positions."""
    snap = _snap()
    alloc = {r["symbol"] for r in snap["dashboard"].get("preset_allocation", [])}
    corr = set(snap["portfolio"]["analysis"]["correlation"]["symbols"])
    assert corr and corr <= alloc                                 # corrélation ⊆ allocation de prod
    # KPI portefeuille cohérents avec le capital initial
    k = snap["dashboard"]["portfolio"]
    assert k["initial"] == 10_000 and round(k["value"] - k["pnl_abs"], 0) == 10_000
