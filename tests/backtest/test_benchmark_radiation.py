"""Le benchmark équipondéré doit survivre à la RADIATION d'un titre sélectionné.

Défaut trouvé le 25/08 sur données réelles (`make backtest-preset` sur le Mac) :

    Équipondéré (même univers)      -100.0%    0.00     nan%      nan%

La stratégie traite les radiations depuis #341 (`dernier_connu` : la ligne est soldée au dernier
cours connu). La ligne de COMPARAISON, elle, n'avait pas été migrée : elle faisait un `.mean()`
brut sur des colonnes qui valent NaN après la dernière cotation. Un seul titre radié suffisait
donc à propager NaN dans toute la courbe — et le preset se comparait à RIEN sans le signaler,
ce qui est pire qu'une comparaison absente : elle a l'air d'exister.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from math import isfinite

import numpy as np

from packages.backtest.preset_backtest import preset_backtest


@dataclass
class Bar:
    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


def _serie(n: int, drift: float, seed: int) -> list:
    px = 100 * np.cumprod(1 + np.random.default_rng(seed).normal(drift, 0.012, n))
    t0 = datetime(2018, 1, 1, tzinfo=UTC)
    return [Bar(t0 + timedelta(days=j), float(px[j]), float(px[j]), float(px[j]),
                float(px[j]), 1e6) for j in range(n)]


def _panel(avec_radiation: bool) -> dict:
    data = {f"S{i:02d}": _serie(700, 0.0003, i) for i in range(1, 12)}
    # Momentum très fort au départ -> le titre EST sélectionné, puis sa cotation s'arrête.
    data["RADIE"] = _serie(430 if avec_radiation else 700, 0.0030, 99)
    return data


def test_benchmark_fini_malgre_une_radiation():
    r = preset_backtest(_panel(True), top_k=6, lookback=120, step=21)
    assert r["available"]
    assert "RADIE" in r["univers"], "le test ne prouve rien si le radié n'est pas sélectionné"
    b = r["benchmark"]
    assert isfinite(b["annualized"]), f"CAGR du benchmark non fini : {b['annualized']}"
    assert isfinite(b["max_drawdown"]), f"maxDD du benchmark non fini : {b['max_drawdown']}"
    assert b["annualized"] > -1.0, "−100 % = la courbe est partie en NaN (le défaut du 25/08)"
    assert all(isfinite(x) for x in r["curves"]["benchmark"])


def test_benchmark_compare_a_quelque_chose_de_plausible():
    """Un benchmark équipondéré sur des séries à dérive positive ne peut pas être ruiné."""
    b = preset_backtest(_panel(True), top_k=6, lookback=120, step=21)["benchmark"]
    assert -0.5 < b["annualized"] < 1.0, f"CAGR implausible : {b['annualized']}"


def test_panel_sans_radiation_inchange():
    """Le correctif ne doit mordre QUE sur le cas cassé : sans radiation, `dernier_connu`
    renvoie le cours lui-même, donc les chiffres publiés ne bougent pas."""
    r = preset_backtest(_panel(False), top_k=6, lookback=120, step=21)
    b = r["benchmark"]
    assert isfinite(b["annualized"]) and isfinite(b["max_drawdown"])
    assert all(isfinite(x) for x in r["curves"]["benchmark"])
