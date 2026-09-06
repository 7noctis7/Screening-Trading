from types import SimpleNamespace
import pytest
from packages.portfolio import user_analysis


def _bars(scale: float):
    return [SimpleNamespace(ts=f"2025-{i // 28 + 1:02d}-{i % 28 + 1:02d}", close=100 + scale * i) for i in range(70)]


def test_analyse_reelle_alignee_et_scenarios(monkeypatch):
    monkeypatch.setattr(user_analysis, "_load", lambda symbol, years: (symbol, _bars(1 if symbol == "AAA" else .5)))
    result = user_analysis.analyze([{"symbol": "AAA", "weight": .6}, {"symbol": "BBB", "weight": .4}])
    assert result["available"] is True
    assert result["n_observations"] == 69
    assert result["alignment"] == "intersection de dates, aucun remplissage"
    assert sum(result["scenarios"]["prudent"]) == pytest.approx(1)


def test_refuse_si_un_historique_manque(monkeypatch):
    monkeypatch.setattr(user_analysis, "_load", lambda symbol, years: (None, []))
    result = user_analysis.analyze([{"symbol": "ABSENT", "weight": 1.0}])
    assert result["available"] is False
    assert result["missing"] == ["ABSENT"]


def test_utilise_les_series_du_snapshot_et_gere_le_cash(monkeypatch):
    monkeypatch.setattr(user_analysis, "_load", lambda symbol, years: (None, []))
    supplied = [{"t": bar.ts, "c": bar.close} for bar in _bars(1)]
    result = user_analysis.analyze([{"symbol": "AAA", "weight": .8},
                                    {"symbol": "CASH:USD", "weight": .2}],
                                   series_by_symbol={"AAA": supplied})
    assert result["available"] is True
    assert result["aliases"]["CASH:USD"] == "CASH:USD"
