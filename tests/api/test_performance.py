"""Payload de la courbe de performance : données RÉELLES seulement, jamais de repli."""

import apps.api.performance as perf

HIST = [{"date": "2026-06-22", "alpaca": 99_000.0, "bitmart": 1_000.0},
        {"date": "2026-06-23", "alpaca": 99_500.0, "bitmart": 1_000.0},
        {"date": "2026-06-24", "alpaca": 101_000.0, "bitmart": 1_000.0}]


def _prix(monkeypatch, table):
    """`_serie_prix` remplacée : aucun accès disque, le test reste hors-ligne."""
    monkeypatch.setattr(perf, "_serie_prix",
                        lambda alias, d, f: table.get(alias, ([], [])))


def test_le_payload_compare_en_dollars_depuis_le_premier_point(monkeypatch):
    monkeypatch.setattr("packages.execution.equity_history._load", lambda: HIST)
    _prix(monkeypatch, {"^GSPC": (["2026-06-22", "2026-06-24"], [400.0, 440.0])})

    r = perf.payload()
    assert r["disponible"] is True
    assert r["depuis"] == "2026-06-22" and r["jusqu_a"] == "2026-06-24"
    assert r["serie"][0]["v"] == 100_000.0            # les deux comptes sommés
    assert r["benchmarks"]["S&P 500"][-1]["v"] == 110_000.0   # 100 000 × 440/400
    # 100 000 → 102 000 : les DEUX comptes, pas le seul Alpaca
    assert r["performances"]["Portefeuille"]["variation"] == 2_000.0


def test_une_reference_INTROUVABLE_est_nommee_jamais_simulee(monkeypatch):
    """Le mandat données-réelles : un utilisateur qui compare son compte à un indice ne
    peut pas deviner que l'indice a été simulé. Absente et nommée, ou rien."""
    monkeypatch.setattr("packages.execution.equity_history._load", lambda: HIST)
    _prix(monkeypatch, {"^GSPC": (["2026-06-22"], [400.0])})

    r = perf.payload()
    assert list(r["benchmarks"]) == ["S&P 500"]
    assert r["ecartees"] == ["Bitcoin", "Nasdaq 100"]


def test_le_premier_alias_QUI_COUVRE_le_debut_est_retenu(monkeypatch):
    """`^NDX` d'abord, `QQQ` en repli — mais un `^NDX` qui démarre trop tard doit
    laisser la place à `QQQ`, sinon le repli ne sert jamais."""
    _prix(monkeypatch, {"^NDX": (["2026-07-01"], [500.0]),          # trop tard
                        "QQQ": (["2026-06-20", "2026-06-24"], [100.0, 105.0])})
    dates, closes = perf._reference(["^NDX", "^IXIC", "QQQ"],
                                    "2026-06-22", "2026-06-24")
    assert (dates, closes) == (["2026-06-20", "2026-06-24"], [100.0, 105.0])


def test_moins_de_deux_points_ne_produit_PAS_de_graphe(monkeypatch):
    """Un seul point d'equity ne fait pas une performance. Le dire, plutôt que tracer
    une courbe plate qui laisserait croire à une mesure."""
    monkeypatch.setattr("packages.execution.equity_history._load",
                        lambda: [{"date": "2026-06-22", "alpaca": 99_000.0}])
    r = perf.payload()
    assert r["disponible"] is False and r["benchmarks"] == {}
    assert "deux points" in r["motif"]


def test_une_equity_NULLE_ou_negative_est_ignoree(monkeypatch):
    """Un compte à 0 $ (broker déconnecté, lecture ratée) n'écrase pas le total."""
    monkeypatch.setattr("packages.execution.equity_history._load", lambda: [
        {"date": "2026-06-22", "alpaca": 99_000.0, "bitmart": 0.0},
        {"date": "2026-06-23", "alpaca": 99_500.0, "bitmart": None}])
    _prix(monkeypatch, {})
    assert [p["v"] for p in perf.payload()["serie"]] == [99_000.0, 99_500.0]
