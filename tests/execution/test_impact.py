"""Impact non linéaire : la taille et la volatilité comptent, pas seulement le notionnel."""
from packages.execution.impact import (
    admit_signal,
    bucket_sigma_bps,
    bucket_volume,
    max_qty_for_budget,
    no_trade_band,
    participation_cap,
    square_root_impact_bps,
    total_cost_bps,
)


def test_impact_croit_en_racine_carree_pas_lineairement():
    a = square_root_impact_bps(1_000, 100_000, 100.0)
    b = square_root_impact_bps(4_000, 100_000, 100.0)     # ×4 en taille
    assert abs(b / a - 2.0) < 1e-9                        # ×2 en coût (racine)
    assert square_root_impact_bps(0, 100_000, 100.0) == 0.0


def test_vol_et_volume_de_la_FENETRE_pas_de_la_journee():
    # 1 h de séance ≈ 390/60 → vol ÷ √6,5 et volume ÷ 6,5 par rapport au jour
    assert abs(bucket_sigma_bps(0.02, 60) - 200.0 * (60 / 390) ** 0.5) < 1e-9
    assert abs(bucket_volume(1_000_000, 60) - 1_000_000 * 60 / 390) < 1e-6
    jour = square_root_impact_bps(10_000, bucket_volume(1e6, 390),
                                  bucket_sigma_bps(0.02, 390))
    heure = square_root_impact_bps(10_000, bucket_volume(1e6, 60),
                                   bucket_sigma_bps(0.02, 60))
    assert heure > jour                                   # même ordre, 1 h = bien plus cher


def test_cout_total_decompose_et_participation():
    c = total_cost_bps(qty=50_000, adv_shares=1_000_000, sigma_daily=0.02,
                       spread_bps=4.0, fee_bps=1.0, minutes=390)
    assert c["half_spread_bps"] == 2.0 and c["fee_bps"] == 1.0
    assert c["impact_bps"] > 0
    assert abs(c["participation"] - 0.05) < 1e-9
    assert abs(c["total_bps"] - (3.0 + c["impact_bps"])) < 1e-6


def test_taille_max_sous_budget_est_l_inverse_du_cout():
    q = max_qty_for_budget(budget_bps=20.0, adv_shares=1_000_000, sigma_daily=0.02,
                           spread_bps=4.0, fee_bps=1.0, minutes=390)
    c = total_cost_bps(q, 1_000_000, 0.02, 4.0, 1.0, minutes=390)
    assert abs(c["total_bps"] - 20.0) < 1e-3              # cohérence aller/retour
    assert max_qty_for_budget(2.0, 1e6, 0.02, 4.0, 1.0) == 0.0   # budget < spread → 0


def test_plafond_de_participation_est_une_contrainte_dure():
    assert participation_cap(1_000_000, minutes=60, pov=0.10) == 1_000_000 * 60 / 390 * 0.10


def test_admission_rejette_l_alpha_inferieur_au_cout():
    assert admit_signal(alpha_bps=30.0, cost_bps=5.0, k=2.0)["admitted"] is True
    ko = admit_signal(alpha_bps=8.0, cost_bps=5.0, k=2.0)
    assert ko["admitted"] is False and ko["edge_after_cost_bps"] < 0 and ko["reason"]


def test_bande_de_non_trading_croit_avec_le_cout():
    assert no_trade_band(10.0, 100.0) > no_trade_band(1.0, 100.0)
    assert no_trade_band(10.0, 0.0) == 0.0
