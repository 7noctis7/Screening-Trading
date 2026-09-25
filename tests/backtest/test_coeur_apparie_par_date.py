"""QML-004 — le cœur indiciel (QQQ) s'apparie au preset PAR DATE, jamais par position.

`blend_equity_multi` collait la queue des rendements de QQQ (calendrier des indices) sur celle
du preset (grille commune de ses 12 titres) : `core_ret[-k:] = cr[-k:]`. `_serie_coeur`, dans
le ledger, prenait `closes[-L:]`. Une seule séance d'écart entre les deux calendriers décalait
TOUT l'historique antérieur — et c'est sur ces courbes que « 50 % QQQ » avait été choisi.
"""

import pytest


def test_valeurs_sur_axe_reporte_le_passe_seulement():
    from packages.backtest.panel import valeurs_sur_axe
    v = valeurs_sur_axe([10.0, 11.0, 12.0], ["2020-01-02", "2020-01-03", "2020-01-06"],
                        ["2020-01-01", "2020-01-03", "2020-01-04", "2020-01-06T00:00:00"])
    assert v == [None, 11.0, 11.0, 12.0]


def test_le_blend_apparie_par_date():
    """QQQ a coté une séance que le preset n'a pas (la 21ᵉ). Chaque pas du blend (cœur à
    100 %) doit rendre le rendement de QQQ entre CES deux dates-là. L'ancien collage par la
    queue décalait d'une séance tout ce qui précède."""
    from datetime import date, timedelta

    from packages.backtest.index_core import blend_equity_multi
    dates_q = [(date(2020, 1, 1) + timedelta(days=k)).isoformat() for k in range(41)]
    qqq = [100.0 * (1.0 + 0.01 * ((k * 7) % 5)) + k for k in range(41)]
    dates_p = dates_q[:20] + dates_q[21:]                         # le preset saute la 21ᵉ
    eq, _ = blend_equity_multi([100.0] * 40, [(qqq, 1.0, dates_q)], init_cap=100.0,
                               dates=dates_p)
    px = dict(zip(dates_q, qqq, strict=True))
    for k in range(39):
        attendu = px[dates_p[k + 1]] / px[dates_p[k]] - 1
        assert eq[k + 1] / eq[k] - 1 == pytest.approx(attendu, abs=2e-4), k


def test_sans_dates_le_comportement_historique_est_conserve():
    from packages.backtest.index_core import blend_equity_multi
    preset = [100.0 + k for k in range(40)]
    qqq = [50.0 + k for k in range(40)]
    a, _ = blend_equity_multi(preset, [(qqq, 0.5)], init_cap=100.0)
    assert a is not None and len(a) == 40


def test_le_ledger_valorise_le_coeur_a_la_bonne_date():
    from packages.backtest.preset_compta import _serie_coeur
    dts = ["2020-01-02", "2020-01-06", "2020-01-07"]
    cc = list(range(300, 560))
    from datetime import date, timedelta
    cdates = [(date(2019, 1, 1) + timedelta(days=k)).isoformat() for k in range(len(cc) - 3)]
    cdates += ["2020-01-02", "2020-01-03", "2020-01-06"]
    arr, _ = _serie_coeur(cc, 0.5, 3, dates=dts, core_dates=cdates)
    assert list(arr) == [557.0, 559.0, 559.0]     # 06/01 lu à SA date ; 07/01 = dernier connu
