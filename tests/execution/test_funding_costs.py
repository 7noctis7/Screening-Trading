"""Portage : ce que le backtest long-short oublie, et qui décide de la rentabilité."""
from packages.execution.funding_costs import (breakeven_gross_bps, carry_costs,
                                              max_borrow_fee, net_expected_return)

NAV = 1_000_000.0


def test_portefeuille_non_leverage_ne_paie_pas_de_marge():
    r = carry_costs(NAV, long_notional=800_000, short_notional=0, initial_margin=0.0)
    assert r["borrowed"] == 0.0 and r["margin_cost_bps"] == 0.0
    assert r["idle_cash_yield_bps"] > 0                 # les 200 k$ oisifs rapportent
    assert r["gross_leverage"] == 0.8


def test_levier_declenche_le_cout_de_financement():
    r = carry_costs(NAV, long_notional=1_500_000, short_notional=0, margin_rate=0.055,
                    initial_margin=0.0)
    assert r["borrowed"] == 500_000
    # 500 k$ à 5,5 % sur 365/360 → ≈ 279 bps du NAV
    assert -290 < r["margin_cost_bps"] < -270


def test_rebate_positif_quand_le_titre_est_facile_a_emprunter():
    r = carry_costs(NAV, 1_000_000, 1_000_000, reference_rate=0.045, borrow_fee=0.005,
                    initial_margin=0.0)
    assert r["short_rebate_bps"] > 0 and r["hard_to_borrow"] is False


def test_hard_to_borrow_inverse_le_signe_et_tue_l_edge():
    facile = carry_costs(NAV, 1_000_000, 1_000_000, borrow_fee=0.005, initial_margin=0.0)
    dur = carry_costs(NAV, 1_000_000, 1_000_000, borrow_fee=0.20, initial_margin=0.0)
    assert dur["hard_to_borrow"] is True
    assert dur["short_rebate_bps"] < 0
    assert dur["total_carry_bps"] < facile["total_carry_bps"] - 1000   # > 10 % de NAV d'écart


def test_capital_bloque_a_un_cout_meme_sans_levier():
    sans = carry_costs(NAV, 500_000, 500_000, initial_margin=0.0)
    avec = carry_costs(NAV, 500_000, 500_000)          # marge Reg-T par défaut = 50 % du brut
    assert avec["capital_opportunity_bps"] < 0
    assert avec["total_carry_bps"] < sans["total_carry_bps"]


def test_dividende_de_la_jambe_courte_est_un_decaissement():
    r = carry_costs(NAV, 0, 1_000_000, short_dividend_yield=0.03, initial_margin=0.0)
    assert r["short_dividend_bps"] < 0


def test_equation_de_rendement_net():
    n = net_expected_return(gross_return_bps=300, trading_cost_bps=80, carry_bps=-150)
    assert n["net_bps"] == 70 and n["profitable"] is True
    ko = net_expected_return(300, 80, -260)
    assert ko["profitable"] is False
    assert breakeven_gross_bps(80, -150) == 230
    assert breakeven_gross_bps(80, -150, margin=2.0) == 460


def test_frais_d_emprunt_maximal_supportable():
    f = max_borrow_fee(gross_alpha_bps=300, trading_cost_bps=50, short_notional=1_000_000,
                       nav=NAV, reference_rate=0.045)
    assert 0.0 < f < 0.30
    # au seuil exact, la jambe de financement du short annule tout juste l'alpha net :
    seuil = carry_costs(NAV, 0, 1_000_000, borrow_fee=f, initial_margin=0.0)
    assert abs(net_expected_return(300, 50, seuil["short_rebate_bps"])["net_bps"]) < 1.0
    # au-delà, le prêteur capte tout l'edge :
    dur = carry_costs(NAV, 0, 1_000_000, borrow_fee=f + 0.05, initial_margin=0.0)
    assert net_expected_return(300, 50, dur["short_rebate_bps"])["profitable"] is False
    assert max_borrow_fee(300, 50, 0, NAV) is None
    assert max_borrow_fee(30, 50, 1_000_000, NAV) == 0.0     # alpha < coûts : aucun short
