"""QML-003 — la courbe du tableau de bord et le ledger exécutent au close SUIVANT la décision.

`preset_backtest` était passé à `exec_lag = 1` le 25/08 (#342) ; `preset_equity_daily`,
`preset_ledger` et `preset_trade_log` — ce que le tableau de bord affiche, et ce qui avait servi
à choisir « 50 % QQQ » — exécutaient encore au cours qui avait servi à décider (blackout lu
sur `A[t]/A[t-2]`, covariance jusqu'à `t`, achat au prix `A[t]`).
"""

from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from packages.core.models import Bar


def _panel(n=20, jours=400, graine=5):
    rng = np.random.default_rng(graine)
    d0 = datetime(2019, 1, 1, tzinfo=UTC)
    return {f"T{k:02d}": [Bar(f"T{k:02d}", "1d", d0 + timedelta(days=i), p, p, p, p, 1e6)
                          for i, p in enumerate(30 * np.exp(np.cumsum(
                              rng.normal(0.0004, 0.02, jours))))]
            for k in range(n)}


def test_le_jour_de_la_premiere_decision_ne_porte_aucun_rendement():
    from packages.backtest.preset_curves import preset_equity_daily
    r = preset_equity_daily(_panel(), init_cap=10_000.0)
    assert r["available"]
    assert r["equity"][1] == pytest.approx(10_000.0)   # décidé au close t, rien détenu t→t+1


def test_le_ledger_achete_au_cours_du_lendemain():
    from packages.backtest.preset_compta import preset_ledger
    data = _panel()
    r = preset_ledger(data, init_cap=10_000.0, max_trades=10_000)
    assert r["available"]
    premier = min(t["date"] for t in r["trades"])
    assert premier > r["dates"][0]                      # jamais au jour de la décision
    t = next(x for x in r["trades"] if x["date"] == premier)
    px = {b.ts.date().isoformat(): b.close for b in data[t["symbol"]]}
    assert t["price"] == pytest.approx(px[premier[:10]], abs=0.01)


def test_le_journal_des_trades_date_a_l_execution():
    from packages.backtest.preset_curves import preset_equity_daily, preset_trade_log
    data = _panel()
    eq, tl = preset_equity_daily(data), preset_trade_log(data)
    assert min(t["date"] for t in tl["trades"]) > eq["dates"][0]
