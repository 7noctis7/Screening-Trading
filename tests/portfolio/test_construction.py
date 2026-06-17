import numpy as np
from packages.portfolio.construction import build_target, vol_target_from_drawdown


def test_vol_target_from_dd():
    assert abs(vol_target_from_drawdown(0.25) - 0.1) < 1e-9   # 0.25/2.5


def test_build_target_exposure_scales_with_dd():
    cov = [[0.04, 0.0, 0.0], [0.0, 0.09, 0.0], [0.0, 0.0, 0.16]]
    syms = ["A", "B", "C"]
    low = build_target(syms, cov, dd_target=0.10, band=0.0)
    high = build_target(syms, cov, dd_target=0.40, band=0.0, max_gross=2.0)
    assert low["available"] and high["available"]
    assert high["gross_exposure"] >= low["gross_exposure"]    # plus de DD toléré → plus d'expo
    assert low["gross_exposure"] <= 1.0


def test_no_trade_band_keeps_current():
    cov = [[0.04, 0.0], [0.0, 0.04]]
    r = build_target(["A", "B"], cov, {"A": 0.5, "B": 0.5}, dd_target=0.25, band=0.99)
    # bande énorme → on garde l'actuel
    assert all(abs(x["target"] - x["current"]) < 1e-9 for x in r["rows"])
