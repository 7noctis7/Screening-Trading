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


# ── Régressions du 06/09 : l'étape 4 restait vide sur un univers mixte actions+crypto ──


def test_ticker_crypto_nu_produit_la_variante_usd():
    """`ETH` doit tenter `ETH-USD` : c'est la forme stockée dans data/crypto.db."""
    assert "ETH-USD" in user_analysis._aliases("ETH")
    assert "BTC-USD" in user_analysis._aliases("BTC")
    assert user_analysis._aliases("ETHUSDT")[:2] == ["ETHUSDT", "ETH-USD"]


def test_action_ne_paie_pas_la_variante_crypto(monkeypatch):
    """L'alias nu répond en premier : `-USD` n'est jamais essayé pour une action."""
    essais = []
    monkeypatch.setattr(user_analysis, "load_bars",
                        lambda alias, years=5: essais.append(alias) or _bars(1))
    monkeypatch.setattr(user_analysis, "_bars_crypto", lambda symbole, years: [])
    alias, bars = user_analysis._load("AAPL", 5)
    assert alias == "AAPL" and essais == ["AAPL"]


def test_univers_mixte_actions_et_crypto_nue(monkeypatch):
    """Le cas de la capture : AAPL/NVDA/AMD + ETH nu. ETH ne répond que sous ETH-USD."""
    monkeypatch.setattr(user_analysis, "load_bars", lambda alias, years=5:
                        _bars(1) if alias in {"AAPL", "NVDA", "AMD", "ETH-USD"} else [])
    monkeypatch.setattr(user_analysis, "_bars_crypto", lambda symbole, years: [])
    result = user_analysis.analyze([{"symbol": "AAPL", "weight": 10}, {"symbol": "NVDA", "weight": 40},
                                    {"symbol": "AMD", "weight": 40}, {"symbol": "ETH", "weight": 10}])
    assert result["available"] is True
    assert result["aliases"]["ETH"] == "ETH-USD"


def test_les_trois_scenarios_sont_publies_sous_les_cles_du_front(monkeypatch):
    """Le front lit `dynamique` ; publier `hrp` le rendait introuvable, donc « indisponible »."""
    monkeypatch.setattr(user_analysis, "_load", lambda symbol, years: (symbol, _bars(1 if symbol == "AAA" else .5)))
    result = user_analysis.analyze([{"symbol": "AAA", "weight": .6}, {"symbol": "BBB", "weight": .4}])
    assert set(result["scenarios"]) == {"prudent", "neutre", "dynamique"}
    for poids in result["scenarios"].values():
        assert sum(poids) == pytest.approx(1)


def test_alignement_sans_remplissage_et_etiquette_conforme():
    """Un ffill inventerait des rendements nuls le week-end pour les actions : la
    covariance mixte actions/crypto en sortirait faussée. L'étiquette doit dire le vrai."""
    series = {"ACTION": {"2025-01-01": 10.0, "2025-01-02": 11.0},
              "CRYPTO": {"2025-01-01": 5.0, "2025-01-02": 6.0, "2025-01-03": 7.0}}
    dates, matrix = user_analysis._align(series)
    assert dates == ["2025-01-01", "2025-01-02"]          # le 03 n'est pas comblé
    assert matrix.shape == (2, 2)
    assert user_analysis.ALIGNEMENT == "intersection de dates, aucun remplissage"
