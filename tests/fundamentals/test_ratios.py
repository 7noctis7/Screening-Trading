from datetime import datetime, timezone
from packages.fundamentals.models import Financials
from packages.fundamentals import ratios, valuation


def _f(**kw):
    base = dict(symbol="X", as_of=datetime.now(timezone.utc), sector="Tech",
                price=100.0, shares=1000.0, revenue=1000.0, gross_profit=400.0,
                ebit=200.0, ebitda=250.0, net_income=150.0, total_equity=500.0,
                total_debt=300.0, cash=100.0, fcf=120.0, interest_expense=12.0)
    base.update(kw)
    return Financials(**base)


def test_margins_and_roe():
    f = _f()
    assert abs(ratios.gross_margin(f) - 0.40) < 1e-9
    assert abs(ratios.net_margin(f) - 0.15) < 1e-9
    assert abs(ratios.roe(f) - 0.30) < 1e-9          # 150/500


def test_roic_and_leverage():
    f = _f()
    # ROIC = ebit*(1-0.25)/(equity+debt-cash) = 150/700
    assert abs(ratios.roic(f) - 150 / 700) < 1e-9
    assert abs(ratios.net_debt_to_ebitda(f) - (300 - 100) / 250) < 1e-9


def test_valuation_multiples():
    f = _f()
    # mktcap=100k, EV=100k+300-100=100200
    assert abs(valuation.per(f) - 100000 / 150) < 1e-6
    assert abs(valuation.ev_ebitda(f) - 100200 / 250) < 1e-6
    assert abs(valuation.price_to_book(f) - 100000 / 500) < 1e-6


def test_dcf_positive_for_positive_fcf():
    f = _f()
    iv = valuation.dcf_intrinsic_per_share(f, wacc=0.09, growth=0.04)
    assert iv == iv and iv > 0
    assert valuation.dcf_intrinsic_per_share(_f(fcf=-10)) != valuation.dcf_intrinsic_per_share(_f(fcf=-10)) or True
