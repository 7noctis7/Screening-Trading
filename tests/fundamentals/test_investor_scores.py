from datetime import datetime, timezone
from packages.fundamentals.models import Financials
from packages.fundamentals.investor_scores import investor_scores, graham_score, thiel_score, schwab_score


def _f(**kw):
    base = dict(symbol="X", as_of=datetime.now(timezone.utc), sector="Tech", price=50, shares=1e8,
               revenue=1e9, gross_profit=7e8, ebit=3e8, ebitda=3.5e8, net_income=2.5e8,
               total_equity=9e8, total_debt=5e7, cash=3e8, fcf=3e8, interest_expense=1e6)
    base.update(kw); return Financials(**base)


def test_thiel_high_for_monopoly():
    assert thiel_score(_f()) >= 80          # marges + ROIC + cash élevés


def test_schwab_theme():
    assert schwab_score("Semi-conducteurs") == 100
    assert schwab_score("Conso. de base") == 0


def test_overall_in_range():
    s = investor_scores(_f(), "Intelligence artificielle")
    assert 0 <= s["overall"] <= 100 and set(s) >= {"graham", "fisher", "thiel", "schwab", "overall"}


def test_graham_penalises_expensive():
    cheap = graham_score(_f(price=8))       # PER/PB bas
    pricey = graham_score(_f(price=500))    # PER/PB élevés
    assert cheap >= pricey
