"""Overlays de risque des graphiques TradingView : les chemins jamais parcourus (47 %).

Ce module DESSINE (cône de VaR, barrières du dernier achat, zones de résultats) ; il ne
décide rien. Ce qui compte : il lit l'API, tolère sa panne sans planter, n'écrit que
pour les symboles demandés, et date les zones de résultats au bon jour.
"""

import pytest

from packages.mcp_tradingview import risk_overlays as ro
from packages.mcp_tradingview.store import OverlayStore


def _barres(n: int, depart: float = 100.0) -> list[dict]:
    px = depart
    out = []
    for i in range(n):
        px *= 1.01 if i % 3 else 0.985
        out.append({"t": f"2026-0{1 + i // 28}-{1 + i % 28:02d}", "c": round(px, 4)})
    return out


def test_series_lues_depuis_des_barres():
    barres = [{"t": "2026-01-02T00:00:00", "c": "101.5"}, {"t": "2026-01-03"}]
    t, c = ro._bars_to_series(barres)
    assert t == ["2026-01-02", "2026-01-03"] and c == [101.5, 0.0]


def test_zones_de_resultats_datees_et_filtrees():
    ev = {"earnings": [{"symbol": "aapl", "date": "2026-10-30"},
                       {"symbol": "MSFT", "date": "2026-10-28"},
                       {"symbol": "AAPL", "date": "pas-une-date"},
                       {"symbol": "AAPL"}]}
    (z,) = ro._blackouts_from_events(ev, "AAPL")
    assert (z.start, z.end) == ("2026-10-28", "2026-10-31")    # J−2 → J+1
    assert z.label == "résultats aapl"
    assert ro._blackouts_from_events([], "AAPL") == []          # pas un dict → rien


def test_barrieres_sans_achat_reconnu_ne_dessinent_rien():
    b = _barres(40)
    t, c = ro._bars_to_series(b)
    assert ro.triple_barrier_overlay(t, c, []) == ([], [])
    assert ro.triple_barrier_overlay(t, c, ["1999-01-01"]) == ([], [])
    assert ro.triple_barrier_overlay(t[:3], c[:3], [t[0]]) == ([], [])


def test_barrieres_du_dernier_achat_encadrent_le_prix():
    t, c = ro._bars_to_series(_barres(60))
    bands, marqueurs = ro.triple_barrier_overlay(t, c, [t[10], t[30]], horizon=10)
    assert bands and bands[0].time == t[30]                     # le DERNIER achat
    assert all(b.lower < c[30] < b.upper for b in bands)
    (m,) = marqueurs
    assert m.side == "sell" and m.text.startswith("sortie ")


@pytest.fixture
def store(tmp_path):
    return OverlayStore(tmp_path / "overlays.json")


def _api(monkeypatch, positions, events=None, panne_events=False):
    def get_json(url, timeout=8.0):
        if url.endswith("/api/positions"):
            if positions is None:
                raise ConnectionError("API arrêtée")
            return positions
        if panne_events:
            raise TimeoutError("events lents")
        return events or {}
    monkeypatch.setattr(ro, "_get_json", get_json)


def test_api_injoignable_ne_plante_pas(monkeypatch, store):
    _api(monkeypatch, None)
    out = ro.populate_from_api(store=store)
    assert out["available"] is False and "injoignable" in out["error"]
    assert store.all() == {}


def test_overlays_ecrits_pour_les_positions_detenues(monkeypatch, store):
    pos = {"real_positions": [{"symbol": "AAA"}, {"symbol": "ZZZ"}],
           "series": {"AAA": _barres(40), "BBB": _barres(40)},
           "markers": {"AAA": [{"t": "2026-01-05", "side": "BUY"}]}}
    _api(monkeypatch, pos, panne_events=True)          # events en panne : toléré
    out = ro.populate_from_api(store=store)
    # ZZZ n'a pas de série, BBB n'est pas détenu
    assert out["available"] and out["tickers"] == ["AAA"]
    ov = store.get("AAA")
    assert ov["bands"] and ov["markers"][0]["side"] == "buy"
    assert ov["source"] == "risk-auto"


def test_tickers_explicites_priment(monkeypatch, store):
    pos = {"real_positions": [{"symbol": "AAA"}],
           "series": {"AAA": _barres(40), "BBB": _barres(40)}}
    resultats = {"earnings": [{"symbol": "BBB", "date": "2026-02-10"}]}
    _api(monkeypatch, pos, events=resultats)
    out = ro.populate_from_api(store=store, tickers=["BBB"])
    assert out["tickers"] == ["BBB"] and store.get("BBB")["blackouts"]


def test_mode_hors_ligne_lit_le_snapshot_en_cache(monkeypatch, store):
    snap = {"dashboard": {"chart_series": {"AAA": _barres(40)}, "real_markers": {}},
            "live": {"real": {"positions": [{"symbol": "AAA"}]}}}
    monkeypatch.setattr(ro, "_load_cached_snapshot", lambda: snap)
    import packages.events as ev
    def panne(syms):
        raise OSError("calendrier des résultats injoignable")
    monkeypatch.setattr(ev, "earnings_for", panne, raising=False)
    out = ro.populate_from_snapshot(store=store)
    assert out == {"available": True, "tickers": ["AAA"], "n": 1, "mode": "offline"}
    assert store.get("AAA")["source"] == "risk-auto-cron"


def test_mode_hors_ligne_sans_snapshot_le_dit(monkeypatch, store):
    monkeypatch.setattr(ro, "_load_cached_snapshot", lambda: None)
    import apps.api.snapshot as snapshot
    monkeypatch.setattr(snapshot, "build_snapshot",
                        lambda: (_ for _ in ()).throw(MemoryError("OOM")))
    out = ro.populate_from_snapshot(store=store)
    assert out["available"] is False and "snapshot indisponible" in out["error"]
