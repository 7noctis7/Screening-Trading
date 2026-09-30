"""grid_runner — grille multi-horizons : rééchantillonnage causal, menus pré-enregistrés,
métriques (Calmar, turnover, DSR), rapport Markdown honnête sur ce qui n'est pas testable."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import numpy as np
import pytest

from packages.core.models import Bar


def _bars(n=900, graine=0, sym="X"):
    rng = np.random.default_rng(graine)
    c = 100 * np.exp(np.cumsum(rng.normal(0.0005, 0.02, n)))
    o = c * (1 + rng.normal(0, 0.003, n))
    j = [d for d in (date(2018, 1, 1) + timedelta(days=k) for k in range(n * 2))
         if d.weekday() < 5][:n]
    return [Bar(sym, "1d", datetime(d.year, d.month, d.day, tzinfo=UTC), o[i],
                max(o[i], c[i]) * 1.01, min(o[i], c[i]) * 0.99, c[i], 1e6)
            for i, d in enumerate(j)]


def test_reechantillonnage_hebdo_et_mensuel():
    from packages.backtest.grid_runner import reechantillonner
    bars = _bars(60)
    s = reechantillonner(bars, "weekly")
    assert s[0].timeframe == "1w"
    premiere = [b for b in bars if b.ts.isocalendar()[:2] == bars[0].ts.isocalendar()[:2]]
    assert (s[0].open, s[0].close) == (premiere[0].open, premiere[-1].close)
    assert s[0].high == max(b.high for b in premiere) and s[0].ts == premiere[-1].ts
    m = reechantillonner(bars, "monthly")
    assert len(m) == len({(b.ts.year, b.ts.month) for b in bars})
    assert reechantillonner(bars, "daily") is bars


def test_reechantillonnage_causal():
    """Une barre hebdomadaire n'existe qu'à la dernière séance de sa semaine : rien de la
    semaine suivante n'y entre, et tronquer l'avenir ne change pas les semaines closes."""
    from packages.backtest.grid_runner import reechantillonner
    bars = _bars(120)
    complet = reechantillonner(bars, "weekly")
    tronque = reechantillonner(bars[:73], "weekly")
    fermees = [b for b in tronque if b.ts < bars[72].ts]
    assert [(b.ts, b.close, b.high) for b in fermees] == \
        [(b.ts, b.close, b.high) for b in complet[:len(fermees)]]


def test_menus_et_filtres():
    from packages.backtest.grid_runner import charger_menus, menus_actifs
    g = charger_menus()
    assert set(g["menus"]) == {"court", "moyen", "long"}
    m = menus_actifs(g, horizons=["1y", "10y"], rebalance=["daily", "yearly"])
    assert set(m) == {"court", "long"}
    assert m["court"]["frequences"] == ["jour"] and m["long"]["frequences"] == ["annee"]
    with pytest.raises(ValueError):
        menus_actifs(g, horizons=["2y"], rebalance=["daily"])


def test_calmar_et_turnover():
    from packages.backtest.scenarios_horizons import risque_et_rotation
    from packages.backtest.signal_long_tp import Trade
    r = {"equity": [100.0, 110.0, 120.0],
         "dates": ["2020-01-01", "2020-07-01", "2021-01-01"],
         "trades": [Trade("2020-01-01", "2020-07-01", 1, 1, 100.0, 10.0, 0.1, 182)]}
    k = {"cagr": 0.20, "max_drawdown": -0.10}
    x = risque_et_rotation(k, r)
    assert x["calmar"] == pytest.approx(2.0)
    assert x["turnover_annuel"] == pytest.approx((100 + 110) / 110.0 / (366 / 365.25))


def test_grille_de_bout_en_bout_et_rapport(tmp_path):
    from packages.backtest.grid_runner import executer_grille, rapport_markdown
    univers = {"A": _bars(graine=1, sym="A"), "B": _bars(graine=2, sym="B")}
    res = executer_grille(univers, {"A": "equity", "B": "equity"}, debut="2018-06-01",
                          timeframes=["daily", "weekly"], horizons=["1y", "3y"],
                          rebalance=["daily", "weekly", "monthly", "quarterly"],
                          n_prior=0)
    assert {"court", "moyen"} <= {b["menu"] for b in res["blocs"]}
    ligne = res["blocs"][0]["top"][0]
    assert {"sharpe", "dsr_median", "max_drawdown", "calmar", "win_rate", "profit_factor",
            "turnover_annuel"} <= set(ligne)
    md = rapport_markdown(res, source="test")
    assert "UNCALIBRATED" in md and "| Horizon" in md and "PBO" in md
    (tmp_path / "r.md").write_text(md, encoding="utf-8")


def test_plan_retire_les_frequences_plus_fines_que_la_barre():
    """Décider chaque jour sur une barre mensuelle relit la même barre : doublon mécanique,
    pas un essai de plus (sinon le DSR serait déflaté par des copies)."""
    from packages.backtest.grid_runner import charger_menus, menus_actifs, plan
    m = menus_actifs(charger_menus(), list(("1y", "3y", "5y", "10y")),
                     ["daily", "weekly", "monthly", "quarterly", "yearly"])
    p = {(tf, nom): (reg["frequences"], n) for tf, nom, reg, n in
         plan(m, ["daily", "weekly", "monthly"], 2)}
    assert p[("weekly", "court")][0] == ["semaine"]
    assert ("monthly", "court") not in p
    assert p[("daily", "court")][1] == 6 * 4 * 2 * 2


def test_configuration_sans_trade_exclue_du_classement():
    from packages.backtest.grid_runner import _top
    h = {1: {"rend_annuel_median": 0.0, "part_bat_bh": 0.0}}
    lignes = [{"id": "vide", "trades": 0, "sharpe": 0.0, "horizons": h},
              {"id": "vraie", "trades": 3, "sharpe": -0.2, "horizons": h}]
    top, vides = _top(lignes, {}, [1])
    assert [t["id"] for t in top] == ["vraie"] and vides == 1
