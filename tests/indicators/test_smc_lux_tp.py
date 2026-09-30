"""SMCLXTP-A (SMC Zones + pivots LuxAlgo) — la traduction Python doit être CAUSALE.

La traduction fournie datait chaque swing SMC à la barre du PIVOT, en le confirmant avec
les `swing_length` barres qui le SUIVENT : les zones Premium/Equilibrium/Discount d'une
barre dépendaient des 50 barres futures. En Pine, `ta.pivothigh(L, L)` ne rend le pivot
qu'à la barre de CONFIRMATION, L barres plus tard. Le premier test rejoue la logique
fournie et montre qu'elle change le PASSÉ quand on change l'AVENIR ; les suivants
verrouillent la version corrigée.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd

from packages.core.models import Bar
from packages.indicators.smc_lux_tp import SMCLuxTPIndicator, calculer


def _ohlc(n=400, graine=0):
    rng = np.random.default_rng(graine)
    c = 100 * np.exp(np.cumsum(rng.normal(0, 0.02, n)))
    h = c * (1 + rng.uniform(0, 0.01, n))
    lo = c * (1 - rng.uniform(0, 0.01, n))
    return h, lo, c


def _bars(h, lo, c):
    d0 = datetime(2020, 1, 1, tzinfo=UTC)
    return [Bar("X", "1d", d0 + timedelta(days=i), c[i], h[i], lo[i], c[i], 1e6)
            for i in range(len(c))]


def _zones_de_la_traduction_fournie(h, lo, L):
    """Logique d'origine (étape 1 et 2 du code fourni), recopiée pour la preuve."""
    n = len(h)
    ph, pl = np.full(n, np.nan), np.full(n, np.nan)
    for i in range(L, n - L):
        if h[i] == np.max(h[i - L:i + L + 1]):
            ph[i] = h[i]
        if lo[i] == np.min(lo[i - L:i + L + 1]):
            pl[i] = lo[i]
    top, last_h, last_l = np.full(n, np.nan), np.nan, np.nan
    for i in range(n):
        last_h = ph[i] if not np.isnan(ph[i]) else last_h
        last_l = pl[i] if not np.isnan(pl[i]) else last_l
        if last_h > last_l:
            top[i] = last_h
    return top


def test_la_traduction_fournie_regardait_l_avenir():
    """Pour AU MOINS une date, ajouter l'avenir change les zones du passé. Le défaut ne se
    voit que si un pivot tombe dans les L barres précédant la date : d'où le balayage."""
    h, lo, _ = _ohlc()
    complet = _zones_de_la_traduction_fournie(h, lo, 20)
    differe = [t for t in range(60, 399, 3)
               if not np.allclose(complet[:t + 1],
                                  _zones_de_la_traduction_fournie(h[:t + 1], lo[:t + 1], 20),
                                  equal_nan=True)]
    assert differe


def test_la_version_corrigee_ne_lit_que_le_passe():
    """Toutes les dates, toutes les sorties : le passé ne bouge jamais."""
    h, lo, c = _ohlc()
    complet = calculer(h, lo, c, swing_length=20, pivot_length=15)
    for t in range(60, 400, 3):
        tronque = calculer(h[:t + 1], lo[:t + 1], c[:t + 1], swing_length=20,
                           pivot_length=15)
        for cle, serie in tronque.items():
            np.testing.assert_array_equal(complet[cle][:t + 1], serie,
                                          err_msg=f"{cle} à t={t}")


def test_un_sommet_n_existe_qu_a_sa_confirmation():
    n, L, j = 60, 5, 30
    h = np.full(n, 10.0) + np.arange(n) * 1e-3
    h[j] = 50.0
    lo, c = h - 1.0, h - 0.5
    r = calculer(h, lo, c, swing_length=L, pivot_length=L)
    assert np.isnan(r["swing_high"][:j + L]).all()                  # rien avant…
    assert r["swing_high"][j + L] == 50.0                           # …sa confirmation
    assert r["take_profit_signal"][j + L]
    assert not r["take_profit_signal"][:j + L].any()


def test_une_serie_plate_n_a_aucun_pivot():
    """`== max(fenêtre)` déclarait un pivot à CHAQUE barre d'une série plate."""
    n = 80
    h, lo, c = np.full(n, 10.0), np.full(n, 9.0), np.full(n, 9.5)
    r = calculer(h, lo, c, swing_length=5, pivot_length=5)
    assert not r["long_signal"].any() and not r["take_profit_signal"].any()
    assert np.isnan(r["range_top"]).all()


def test_formules_des_zones_et_ratio():
    h, lo, c = _ohlc(graine=3)
    r = calculer(h, lo, c, swing_length=10, pivot_length=10)
    ok = ~np.isnan(r["range_top"])
    assert ok.any()
    top, bas = r["range_top"][ok], r["range_bottom"][ok]
    np.testing.assert_allclose(r["premium_bottom"][ok], 0.95 * top + 0.05 * bas)
    np.testing.assert_allclose(r["discount_top"][ok], 0.95 * bas + 0.05 * top)
    np.testing.assert_allclose(r["eq_mid"][ok], 0.5 * (top + bas))
    attendu = (c[ok] - r["discount_top"][ok]) / (r["premium_bottom"][ok] - r["discount_top"][ok])
    np.testing.assert_allclose(r["smc_zone_ratio"][ok], attendu)


def test_le_ratio_ne_depend_pas_de_l_echelle_des_prix():
    h, lo, c = _ohlc(graine=4)
    a = calculer(h, lo, c, swing_length=10, pivot_length=10)["smc_zone_ratio"]
    b = calculer(7 * h, 7 * lo, 7 * c, swing_length=10, pivot_length=10)["smc_zone_ratio"]
    np.testing.assert_allclose(a, b, equal_nan=True)


def test_pivots_manques_et_etat_initial():
    """Deux sommets consécutifs → un creux manqué (signal LONG au 2ᵉ sommet). Le tout
    premier pivot n'est JAMAIS « manqué » : la traduction partait d'un état « creux »
    fictif et déclarait un TP manqué au premier creux venu."""
    L = 3
    h = np.array([5, 5, 5, 9, 5, 5, 5, 5, 5, 9.5, 5, 5, 5, 5, 5], float)
    h += np.arange(h.size) * 1e-4
    lo = h - 1.0
    lo[:] = np.linspace(4.0, 4.5, h.size)                     # aucun creux strict
    r = calculer(h, lo, h - 0.5, swing_length=L, pivot_length=L)
    assert r["take_profit_signal"][3 + L] and r["take_profit_signal"][9 + L]
    assert r["long_signal"][9 + L]                            # creux manqué
    assert not r["long_signal"][3 + L]                        # 1er pivot : rien de manqué
    sans = calculer(h, lo, h - 0.5, swing_length=L, pivot_length=L, pivots_manques=False)
    assert not sans["long_signal"].any()


def test_registre_et_interface_dataframe():
    from packages.indicators import indicators
    h, lo, c = _ohlc(n=200)
    bars = _bars(h, lo, c)
    assert {"smc_zone_ratio", "smclxtp_long", "smclxtp_tp"} <= set(indicators.names())
    ratio = indicators.create("smc_zone_ratio", swing_length=10).compute(bars)
    assert len(ratio) == len(bars) and np.isnan(ratio[0])
    df = pd.DataFrame({"open": c, "high": h, "low": lo, "close": c})
    out = SMCLuxTPIndicator(swing_length=10, pivot_length=10).calculate(df)
    assert {"range_top", "premium_bottom", "eq_mid", "discount_top", "long_signal",
            "take_profit_signal", "smc_zone_ratio"} <= set(out.columns)
    np.testing.assert_allclose(out["smc_zone_ratio"].to_numpy(), ratio, equal_nan=True)
