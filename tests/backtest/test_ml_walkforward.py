import numpy as np
from types import SimpleNamespace
from packages.backtest.ml_walkforward import ml_walkforward


def _bars(closes):
    return [SimpleNamespace(close=float(c)) for c in closes]


def test_walkforward_runs_and_compares():
    rng = np.random.default_rng(0)
    data = {f"S{i}": _bars(100 * np.cumprod(1 + rng.normal(0.0004 + i * 0.00002, 0.02, 360)))
            for i in range(16)}
    r = ml_walkforward(data, step=21, max_assets=16, max_train=2000)
    assert r["available"]
    for k in ("ml", "tech", "benchmark"):
        assert r[k]["available"] and r[k]["max_drawdown"] <= 0
        assert 0.0 <= r[k]["dsr"] <= 1.0


def test_too_few_assets():
    assert ml_walkforward({"A": _bars(range(1, 300))})["available"] is False


def test_le_dsr_est_deflate_par_le_registre_pas_par_30_en_dur(monkeypatch):
    """Audit 17/11 : `n_trials=30/15` ignorait les 5 767 essais du registre."""
    import packages.backtest.preset_backtest as pb
    monkeypatch.setattr(pb, "essais_du_programme", lambda minimum=15: 5767)
    rng = np.random.default_rng(1)
    data = {f"S{i}": _bars(100 * np.cumprod(1 + rng.normal(0.0004, 0.02, 360)))
            for i in range(16)}
    r = ml_walkforward(data, step=21, max_assets=16, max_train=2000)
    assert r["n_essais"] == 5767


def test_le_rendement_part_du_close_d_execution_pas_du_close_du_signal():
    """Audit 17/11 : le rendement partait du close qui avait servi au signal. Un bond de
    TOUS les titres entre le close de la PREMIÈRE décision et le suivant ne doit pas être
    encaissé : aucune position n'est encore prise, elle ne l'est qu'au close de t + 1.

    360 barres, départ 63, pas 21 : la première décision entraînable (6 dates de label)
    tombe à t = 126 ; le bond s'applique dès la barre 127. L'équipondéré ne dépend que des
    prix, donc il doit être IDENTIQUE avec et sans bond."""
    rng = np.random.default_rng(2)
    base = 100 * np.cumprod(1 + rng.normal(0.0004, 0.02, (16, 360)), axis=1)
    saut = base.copy()
    saut[:, 127:] *= 1.5
    kw = dict(step=21, max_assets=16, max_train=2000)
    a = ml_walkforward({f"S{i}": _bars(base[i]) for i in range(16)}, **kw)
    b = ml_walkforward({f"S{i}": _bars(saut[i]) for i in range(16)}, **kw)
    assert a["n_rebalances"] == b["n_rebalances"] == 12
    assert a["benchmark"]["total_return"] == b["benchmark"]["total_return"]
