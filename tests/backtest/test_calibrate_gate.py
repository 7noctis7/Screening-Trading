import numpy as np
from datetime import datetime, timezone, timedelta
from packages.core.models import Bar
from packages.backtest.calibrate import calibrate_preset


def _data(n=600, seed=3):
    rng = np.random.default_rng(seed)
    out = {}
    for i in range(8):
        px = 100 * np.cumprod(1 + rng.normal(0.0004, 0.012, n))
        t0 = datetime(2022, 1, 1, tzinfo=timezone.utc)
        out[f"A{i}"] = [Bar(f"A{i}", "1d", t0 + timedelta(days=k), px[k], px[k], px[k], px[k], 0) for k in range(n)]
    return out


def test_gate_exposes_robust_and_recommended():
    res = calibrate_preset(_data(), {f"A{i}": 1.0 for i in range(8)},
                           dd_targets=(0.15, 0.35), top_ks=(8,), bands=(0.0, 0.06))
    assert res["available"]
    assert "robust" in res and "recommended" in res and "verdict" in res
    # bruit pur → généralement non robuste → recommended = défensif (dd-cible le plus bas)
    if not res["robust"]:
        assert res["recommended"]["dd_target"] == min(r["dd_target"] for r in res["results"])
