from packages.execution.tca import implementation_shortfall, decompose_cost
from packages.execution.frictions import Frictions


def test_shortfall_buy_costs_when_price_rises():
    r = implementation_shortfall(100.0, 101.0, "buy", 10000.0)
    assert r["slippage_bps"] == 100.0 and r["cost_usd"] == 100.0


def test_shortfall_sell_sign():
    r = implementation_shortfall(100.0, 99.0, "sell", 10000.0)
    assert r["slippage_bps"] == 100.0    # vendre moins cher = coût positif


def test_decompose_sums_legacy_bps():
    d = decompose_cost(100000, spread_bps=4, impact_bps=3, fee_bps=1)
    assert d["total_bps"] == 6.0   # 2 (demi-spread) + 3 + 1
    assert abs(d["spread_usd"] + d["impact_usd"] + d["fees_usd"] - d["total_usd"]) < 1e-6
    assert d["source"] == "bps_legacy"


def test_decompose_chemin_prod_passe_par_frictions():
    """Snapshot appelle decompose_cost(drift) SANS bps → Frictions.detail."""
    d = decompose_cost(10_000.0, prix_mid=50.0)
    assert d["source"] == "frictions"
    assert "frictions" in d
    assert abs(d["spread_usd"] + d["impact_usd"] + d["fees_usd"] - d["total_usd"]) < 1e-6
    f = Frictions()
    assert d["total_usd"] == round(f.cout_aller_retour(10_000.0, 50.0), 2)
