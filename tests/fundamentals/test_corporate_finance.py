"""Finance d'entreprise — Vernimmen (ROCE/EVA/DuPont) + Damodaran (WACC/DCF scénarios/inversé)."""
from datetime import datetime, timezone

from packages.fundamentals import corporate_finance as cf
from packages.fundamentals.models import Financials


def _fin(**kw) -> Financials:
    base = dict(symbol="TST", as_of=datetime.now(timezone.utc), sector="Information Technology",
                price=100.0, shares=1e8, revenue=1e9, gross_profit=6e8, ebit=3e8, ebitda=3.5e8,
                net_income=2.2e8, total_equity=5e8, total_debt=1e8, cash=2e8, fcf=2e8,
                interest_expense=4e6)
    base.update(kw)
    return Financials(**base)


def test_capm_cost_of_equity_increases_with_beta():
    assert cf.cost_of_equity(1.5) > cf.cost_of_equity(0.8)
    assert abs(cf.cost_of_equity(1.0, rf=0.04, erp=0.05) - 0.09) < 1e-9


def test_wacc_bounded_and_between_costs():
    f = _fin()
    w = cf.wacc(f, beta=1.1)
    assert 0.05 <= w <= 0.20


def test_roce_and_eva_value_creation():
    f = _fin()
    roce = cf.roce_after_tax(f)
    assert roce > 0
    w = cf.wacc(f, beta=1.0)
    e = cf.eva(f, w)
    # EVA = (ROCE - WACC) * capitaux employés
    assert abs(e - (roce - w) * cf.capital_employed(f)) < 1.0


def test_dupont_identity_holds():
    f = _fin()
    d = cf.dupont(f)
    assert abs(d["net_margin"] * d["asset_turnover"] * d["equity_multiplier"] - d["roe"]) < 1e-9


def test_damodaran_scenarios_ordered():
    f = _fin()
    w = cf.wacc(f, beta=1.0)
    s = cf.damodaran_scenarios(f, w, base_growth=0.08)["scenarios"]
    assert s["bear"] <= s["base"] <= s["bull"]               # plus de croissance → plus de valeur


def test_reverse_dcf_recovers_growth():
    f = _fin()
    w = cf.wacc(f, beta=1.0)
    # on price le titre exactement à sa valeur DCF base(8%) puis on doit retrouver ~8%
    base_val = cf.damodaran_scenarios(f, w, base_growth=0.08)["scenarios"]["base"]
    f2 = _fin(price=base_val)
    g = cf.reverse_dcf_growth(f2, w)
    assert abs(g - 0.08) < 0.01


def test_convert_financials_scales_monetary_only():
    f = _fin(price=462.0, shares=5.2e9, revenue=2.159e12, net_income=1.0e12, total_debt=3e11,
             cash=1.5e12, currency="TWD", price_currency="USD")
    g = cf.convert_financials(f, 0.031)                      # TWD→USD
    assert abs(g.revenue - 2.159e12 * 0.031) < 1            # CA converti
    assert abs(g.net_income - 1.0e12 * 0.031) < 1
    assert g.price == f.price and g.shares == f.shares       # cours & actions inchangés
    assert g.currency == "USD"
    # après conversion, le P/E redevient plausible (capi USD / résultat net USD)
    from packages.fundamentals import valuation
    pe = valuation.per(g)
    assert 5 < pe < 200                                      # plus l'aberration ~1


def test_convert_financials_identity_when_same():
    f = _fin()
    assert cf.convert_financials(f, 1.0) is f                # pas de conversion si fx=1


def test_gearing_negative_when_net_cash():
    f = _fin(total_debt=5e7, cash=2e8)                       # trésorerie nette positive
    assert cf.gearing(f) < 0
