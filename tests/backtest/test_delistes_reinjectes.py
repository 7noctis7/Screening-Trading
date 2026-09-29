"""QML-002 — les titres arrêtés (délistés) restent visibles des backtests.

`build_snapshot` retirait tout titre dont la dernière barre avait plus de dix jours AVANT
tous les consommateurs — donc aussi avant les backtests, qui ne voyaient que des survivants.
Correct pour la production (on ne trade pas un titre radié), faux pour la mesure.
"""

from datetime import UTC, datetime, timedelta

import numpy as np

from packages.core.models import Bar

D0 = datetime(2016, 1, 4, tzinfo=UTC)


def _serie(sym, n, mu, graine, debut=0):
    rng = np.random.default_rng(graine)
    px = 20 * np.exp(np.cumsum(rng.normal(mu, 0.01, n)))
    return [Bar(sym, "1d", D0 + timedelta(days=debut + i), p, p, p, p, 1e6)
            for i, p in enumerate(px)]


def test_separer_perimees():
    from packages.data.survivorship import separer_perimees
    data = {"VIVANT": _serie("VIVANT", 400, 0.0, 1), "RADIE": _serie("RADIE", 200, 0.0, 2)}
    fraiches, perimees = separer_perimees(data, jours=10)
    assert set(fraiches) == {"VIVANT"} and set(perimees) == {"RADIE"}
    assert perimees["RADIE"] is data["RADIE"]          # rien n'est modifié, seulement trié


def test_un_delisté_reinjecte_peut_etre_selectionne_quand_il_cotait():
    """Un titre au meilleur momentum de départ, radié ensuite : le backtest doit pouvoir le
    retenir. Sur un univers de survivants, il n'existe tout simplement pas."""
    from packages.backtest.preset_backtest import preset_backtest
    data = {f"S{k:02d}": _serie(f"S{k:02d}", 900, 0.0002, 10 + k) for k in range(20)}
    data["RADIE"] = _serie("RADIE", 500, 0.004, 99)       # s'envole, puis disparaît
    r = preset_backtest(data, top_k=10)
    assert r["available"] and "RADIE" in r["univers"]
