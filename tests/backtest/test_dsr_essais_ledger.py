"""QML-005 — le DSR publié par `preset_backtest` se déflate par les essais RÉELS du ledger.

`_stats(port, per_year)` prenait `n_trials=15` en dur, quel que soit le nombre de
configurations effectivement essayées sur le même historique (labos, balayages, variantes
d'alignement et de lag). Un DSR sous-déflaté flatte mécaniquement le résultat.
"""

from datetime import UTC, datetime, timedelta

import numpy as np

from packages.core.models import Bar


def _panel():
    rng = np.random.default_rng(4)
    d0 = datetime(2016, 1, 1, tzinfo=UTC)
    return {f"T{k:02d}": [Bar(f"T{k:02d}", "1d", d0 + timedelta(days=i), p, p, p, p, 1e6)
                          for i, p in enumerate(30 * np.exp(np.cumsum(
                              rng.normal(0.0006, 0.012, 900))))]
            for k in range(25)}


def test_le_dsr_publie_utilise_le_nombre_d_essais_du_ledger(monkeypatch):
    import packages.research.ledger as ledger
    from packages.backtest.preset_backtest import preset_backtest
    data = _panel()
    monkeypatch.setattr(ledger, "deflation_params", lambda **_k: (15, None))
    peu = preset_backtest(data)
    monkeypatch.setattr(ledger, "deflation_params", lambda **_k: (400, None))
    beaucoup = preset_backtest(data)
    assert peu["n_essais"] == 15 and beaucoup["n_essais"] == 400
    assert beaucoup["preset"]["dsr"] < peu["preset"]["dsr"]      # plus d'essais, moins de DSR


def test_ledger_illisible_repli_prudent(monkeypatch):
    import packages.research.ledger as ledger
    from packages.backtest.preset_backtest import essais_du_programme

    def _panne(**_k):
        raise OSError("ledger absent")
    monkeypatch.setattr(ledger, "deflation_params", _panne)
    assert essais_du_programme() == 15
