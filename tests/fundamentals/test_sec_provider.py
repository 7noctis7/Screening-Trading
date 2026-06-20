"""SEC EDGAR XBRL : sélection de la dernière valeur annuelle (parsing pur, hors-ligne)."""

from packages.fundamentals.sec_provider import _growth, _latest


def test_latest_prefers_most_recent_annual():
    facts = {"us-gaap": {"Revenues": {"units": {"USD": [
        {"end": "2023-12-31", "val": 100, "form": "10-K", "fp": "FY"},
        {"end": "2024-12-31", "val": 120, "form": "10-K", "fp": "FY"},
        {"end": "2024-09-30", "val": 30, "form": "10-Q", "fp": "Q3"},   # trimestriel ignoré
    ]}}}}
    assert _latest(facts, "Revenues") == 120.0


def test_latest_fallback_concepts_and_missing():
    facts = {"us-gaap": {"SalesRevenueNet": {"units": {"USD": [
        {"end": "2024-12-31", "val": 55, "form": "10-K", "fp": "FY"}]}}}}
    # 1er concept absent → bascule sur le 2e
    assert _latest(facts, "Revenues", "SalesRevenueNet") == 55.0
    assert _latest(facts, "DoesNotExist") is None


def test_latest_uses_quarterly_when_no_annual():
    facts = {"us-gaap": {"NetIncomeLoss": {"units": {"USD": [
        {"end": "2024-03-31", "val": 5, "form": "10-Q", "fp": "Q1"},
        {"end": "2024-06-30", "val": 7, "form": "10-Q", "fp": "Q2"}]}}}}
    assert _latest(facts, "NetIncomeLoss") == 7.0      # plus récent dispo si pas d'annuel


def test_growth_yoy_real_between_two_years():
    facts = {"us-gaap": {"Revenues": {"units": {"USD": [
        {"end": "2023-12-31", "val": 100, "form": "10-K", "fp": "FY"},
        {"end": "2024-12-31", "val": 125, "form": "10-K", "fp": "FY"}]}}}}
    assert abs(_growth(facts, "Revenues") - 0.25) < 1e-9     # +25 % réel, pas une constante
    # un seul exercice → pas de croissance calculable
    one = {"us-gaap": {"Revenues": {"units": {"USD": [
        {"end": "2024-12-31", "val": 100, "form": "10-K", "fp": "FY"}]}}}}
    assert _growth(one, "Revenues") is None
