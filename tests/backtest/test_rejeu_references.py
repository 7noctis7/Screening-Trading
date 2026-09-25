"""Les références du rejeu portent sur les MÊMES dates que lui.

Comparer le rejeu (2016-2026, univers négociable) à l'« équipondéré » de `backtest-preset`
(autre fenêtre, top-30 figé) mélangeait deux périodes et deux univers. Les références
publiées à côté du rejeu sont recalculées sur SES dates : QQQ acheté-conservé, et
l'équipondéré quotidien de tous les titres cotés (rééquilibré chaque jour, sans frais).
"""

import pytest


def test_qqq_achete_conserve_sur_les_dates_du_rejeu():
    from packages.backtest.preset_rejeu import references
    dates = ["2020-01-02", "2020-01-03", "2020-01-06"]
    prix = {"QQQ": {"2020-01-01": 90.0, "2020-01-02": 100.0, "2020-01-03": 110.0,
                    "2020-01-06": 121.0}}
    r = references(prix, dates)
    assert r["QQQ"]["courbe"] == pytest.approx([1.0, 1.1, 1.21])


def test_equipondere_ne_compte_que_les_titres_cotes():
    from packages.backtest.preset_rejeu import references
    dates = ["d1", "d2", "d3"]
    prix = {"A": {"d1": 100.0, "d2": 110.0, "d3": 110.0},
            "B": {"d2": 50.0, "d3": 40.0}}                  # B introduit en d2
    r = references(prix, dates)
    # d1→d2 : seul A coté des deux côtés (+10 %) ; d2→d3 : moyenne(0 %, −20 %) = −10 %
    assert r["équipondéré"]["courbe"] == pytest.approx([1.0, 1.1, 0.99])


def test_sans_qqq_la_reference_est_absente():
    from packages.backtest.preset_rejeu import references
    assert "QQQ" not in references({"A": {"d1": 1.0, "d2": 1.0}}, ["d1", "d2"])
