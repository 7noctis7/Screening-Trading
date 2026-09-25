"""QML-014 — la poche crypto choisit ses paires par DOLLAR-VOLUME, comme sa doc l'annonce.

Le « proxy de liquidité » valait `mean(prix) × std(prix)/mean(prix)` = l'écart-type du prix
en dollars : une paire à 60 000 $ peu échangée battait une paire à 1 $ échangée par
milliards. Le docstring promettait un dollar-volume médian récent.
"""

from datetime import UTC, datetime, timedelta

import numpy as np

from packages.core.models import Bar


def _serie(sym, prix, volume, n=200, graine=0):
    rng = np.random.default_rng(graine)
    d0 = datetime(2023, 1, 1, tzinfo=UTC)
    px = prix * np.exp(np.cumsum(rng.normal(0, 0.03, n)))
    return [Bar(sym, "1d", d0 + timedelta(days=i), p, p, p, p, volume) for i, p in enumerate(px)]


def test_dollar_volume_median():
    from packages.backtest.crypto_sleeve import liquidite
    barres = [Bar("X", "1d", datetime(2023, 1, 1 + i, tzinfo=UTC), 2.0, 2.0, 2.0, 2.0, v)
              for i, v in enumerate([10, 1000, 30])]
    assert liquidite(barres) == 2.0 * 30


def test_une_paire_chere_et_morte_ne_bat_pas_une_paire_echangee():
    from packages.backtest.crypto_sleeve import crypto_weights
    data = {"CHER/USD": _serie("CHER/USD", 60_000.0, 0.01, graine=1),   # ~600 $/jour
            "LIQ/USD": _serie("LIQ/USD", 1.0, 5e8, graine=2),            # ~500 M$/jour
            **{f"C{k}/USD": _serie(f"C{k}/USD", 10.0, 1e7, graine=3 + k) for k in range(4)}}
    w = crypto_weights(data, top_k=4, min_names=2)
    assert "LIQ/USD" in w and "CHER/USD" not in w
