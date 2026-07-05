"""Non-régression P0-1 (fuite d'univers) — verrou permanent.

Les fonctions qui alimentent le DASHBOARD (`preset_equity_daily`, `preset_trade_log`,
`preset_ledger`) et `preset_backtest` doivent sélectionner l'univers par MOMENTUM prix-only
(cf. `_price_universe`), JAMAIS par le score `quality` du jour (look-ahead + biais du survivant).

Principe du test : on lance chaque fonction avec deux dicts `quality` OPPOSÉS (croissant puis
décroissant). Si l'univers dépendait de la qualité, les deux runs choisiraient des titres
différents → sorties différentes. L'anti-fuite exige des sorties **strictement identiques**.
Si ce test casse un jour, c'est que la fuite est revenue.
"""

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from packages.backtest.preset_backtest import (
    preset_backtest,
    preset_equity_daily,
    preset_ledger,
    preset_trade_log,
)


@dataclass
class Bar:
    ts: datetime
    close: float


def _series(n: int, drift: float, vol: float, seed: int) -> list[Bar]:
    import random

    rng = random.Random(seed)
    px, out, t0 = 100.0, [], datetime(2020, 1, 1, tzinfo=timezone.utc)
    for i in range(n):
        px *= math.exp(drift / 252 + vol / math.sqrt(252) * rng.gauss(0, 1))
        out.append(Bar(t0 + timedelta(days=i), px))
    return out


def _data(n=400):
    # drifts variés → l'ordre par momentum diffère de l'ordre S0..S11 (donc de la qualité).
    return {f"S{i}": _series(n, 0.02 + 0.03 * (i % 6), 0.18 + 0.02 * (i % 4), seed=i)
            for i in range(12)}


# Deux qualités antagonistes : si l'univers suivait la qualité, elles divergeraient.
def _q_asc(data):
    return {s: float(i) for i, s in enumerate(data)}


def _q_desc(data):
    return {s: float(len(data) - i) for i, s in enumerate(data)}


def test_equity_daily_universe_ignores_quality():
    data = _data()
    a = preset_equity_daily(data, _q_asc(data), top_k=8)
    b = preset_equity_daily(data, _q_desc(data), top_k=8)
    assert a["available"] and b["available"]
    assert a["equity"] == b["equity"]          # courbe identique = univers indépendant de la qualité
    assert a["dates"] == b["dates"]


def test_trade_log_universe_ignores_quality():
    data = _data()
    a = preset_trade_log(data, _q_asc(data), top_k=8)
    b = preset_trade_log(data, _q_desc(data), top_k=8)
    assert a["available"] and b["available"]
    assert a["trades"] == b["trades"]          # mêmes trades = mêmes titres sélectionnés
    assert a["turnover_annual"] == b["turnover_annual"]


def test_ledger_universe_ignores_quality():
    data = _data()
    a = preset_ledger(data, _q_asc(data), top_k=8)
    b = preset_ledger(data, _q_desc(data), top_k=8)
    assert a["available"] and b["available"]
    assert a["trades"] == b["trades"]


def test_preset_backtest_default_is_leak_free():
    data = _data()
    # défaut (legacy_quality_universe=False) : insensible à la qualité…
    a = preset_backtest(data, _q_asc(data), top_k=8)
    b = preset_backtest(data, _q_desc(data), top_k=8)
    assert a["curves"]["preset"] == b["curves"]["preset"]
    # …alors que le mode legacy (fuite, comparaison seulement) DOIT en dépendre — sinon le test
    # ne prouve rien (les deux univers de qualité sont bien distincts sur ces données).
    la = preset_backtest(data, _q_asc(data), top_k=8, legacy_quality_universe=True)
    lb = preset_backtest(data, _q_desc(data), top_k=8, legacy_quality_universe=True)
    assert la["curves"]["preset"] != lb["curves"]["preset"]
