"""Barres volume / dollar : agrégation exacte, rien d'inventé, et le diagnostic qui
mesure (au lieu de présumer) ce qu'elles améliorent."""

from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from packages.core.models import Bar
from packages.data import barres_info as bi
from packages.ml.labeling import volatilite_garman_klass

T0 = datetime(2024, 1, 1, tzinfo=UTC)


def _b(i, px, vol):
    return Bar("X", "1d", T0 + timedelta(days=i), px, px * 1.01, px * 0.99, px, vol)


def test_barres_volume_conservent_le_volume_et_l_ohlc():
    src = [_b(i, 100 + i, 10) for i in range(10)]
    out = bi.barres_volume(src, 30)
    assert len(out) == 3                                   # 10ᵉ barre : incomplète
    assert [x.volume for x in out] == [30, 30, 30]
    assert out[0].open == 100 and out[0].close == 102
    assert out[0].high == pytest.approx(102 * 1.01) and out[0].low == pytest.approx(99)
    assert out[0].ts == src[2].ts and out[1].ts == src[5].ts


def test_barres_dollar_se_ferment_plus_souvent_quand_l_activite_monte():
    calme = [_b(i, 100, 10) for i in range(10)]
    agite = [_b(10 + i, 100, 100) for i in range(10)]
    out = bi.barres_dollar(calme + agite, 5000)
    fin_calme = sum(1 for x in out if x.ts <= calme[-1].ts)
    # calme : une barre pour 5 séances ; agité : une par séance (une barre d'entrée ne
    # se coupe pas — d'où l'intérêt de données intraday).
    assert fin_calme == 2 and len(out) - fin_calme == 10


def test_seuil_et_entrees_invalides():
    src = [_b(i, 100, 10) for i in range(10)]
    assert bi.seuil_pour(src, 0.5) == pytest.approx(2000)
    with pytest.raises(ValueError):
        bi.barres_volume(src, 0)


def test_diagnostic_iid_detecte_la_variance_qui_se_regroupe():
    rng = np.random.default_rng(0)
    vol = np.repeat([0.005, 0.03], 500)                    # calme puis agité
    px = 100 * np.exp(np.cumsum(rng.normal(0, vol)))
    d = bi.diagnostic_iid(px)
    assert d["available"] and d["autocorr_carres_1"] > 0.1 and d["kurtosis"] > 4
    stable = bi.diagnostic_iid(100 * np.exp(np.cumsum(rng.normal(0, 0.01, 1000))))
    assert abs(stable["autocorr_carres_1"]) < 0.1
    assert bi.diagnostic_iid([1, 2, 3])["available"] is False


def test_garman_klass_croit_avec_l_amplitude_et_ignore_l_illisible():
    n = 60
    calme = volatilite_garman_klass([100] * n, [100.5] * n, [99.5] * n, [100] * n)
    agite = volatilite_garman_klass([100] * n, [103] * n, [97] * n, [100] * n)
    assert agite[-1] > 5 * calme[-1] > 0
    v = volatilite_garman_klass([100, 0], [101, 0], [99, 0], [100, 0])
    assert np.isfinite(v).all()
