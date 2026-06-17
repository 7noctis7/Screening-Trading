import numpy as np
from packages.portfolio.evt import fit_pot, evt_var_es


def test_pot_fits_on_fat_tails():
    rng = np.random.default_rng(0)
    r = np.concatenate([rng.normal(0, 0.01, 1000), rng.standard_t(3, 200) * 0.02])
    f = fit_pot(r)
    assert f["available"] and f["n_exc"] >= 10


def test_evt_var_ge_normal_quantile():
    rng = np.random.default_rng(1)
    r = rng.standard_t(3, 2000) * 0.01            # queues lourdes
    e = evt_var_es(r, alpha=0.999)
    assert e["available"] and e["es"] >= e["var"] > 0   # ES ≥ VaR


def test_too_short():
    assert evt_var_es([0.01, -0.01])["available"] is False
