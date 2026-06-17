from datetime import datetime, timezone
from packages.fundamentals.models import Financials
from packages.fundamentals.scoring import f_score, f_score_label


def _solid():
    return Financials(symbol="X", as_of=datetime.now(timezone.utc), sector="Tech", price=100,
                      shares=1e8, revenue=1e9, gross_profit=6e8, ebit=2.5e8, ebitda=3e8,
                      net_income=2e8, total_equity=8e8, total_debt=1e8, cash=2e8, fcf=2.5e8,
                      interest_expense=1e6)


def _weak():
    return Financials(symbol="Y", as_of=datetime.now(timezone.utc), sector="Tech", price=100,
                      shares=1e8, revenue=1e9, gross_profit=1e8, ebit=-5e7, ebitda=1e7,
                      net_income=-3e7, total_equity=1e8, total_debt=9e8, cash=1e7, fcf=-2e7,
                      interest_expense=5e7)


def test_solid_high_score():
    s = f_score(_solid())
    assert s >= 7 and f_score_label(s) == "solide"


def test_weak_low_score():
    s = f_score(_weak())
    assert s <= 3 and f_score_label(s) == "fragile"
