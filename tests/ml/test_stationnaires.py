"""Variables stationnaires du méta-modèle : stationnarité, causalité, invariance d'échelle.

Données synthétiques UNIQUEMENT pour valider la mathématique (mandat données-réelles)."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import numpy as np
import pytest

from packages.core.models import Bar


def _bars(n=1500, graine=3, echelle=1.0, echelle_vol=1.0):
    """Marche aléatoire à dérive + régimes de volatilité : le prix n'est PAS stationnaire."""
    rng = np.random.default_rng(graine)
    sig = np.repeat(rng.uniform(0.01, 0.03, n // 250 + 1), 250)[:n]
    c = 100 * np.exp(np.cumsum(rng.normal(0.0006, 1.0, n) * sig)) * echelle
    o = c * (1 + rng.normal(0, 0.003, n))
    h = np.maximum(o, c) * (1 + np.abs(rng.normal(0, 0.006, n)))
    lo = np.minimum(o, c) * (1 - np.abs(rng.normal(0, 0.006, n)))
    v = np.exp(rng.normal(13, 0.4, n)) * echelle_vol
    j = [date(2015, 1, 1) + timedelta(days=k) for k in range(n)]
    return [Bar("X", "1d", datetime(d.year, d.month, d.day, tzinfo=UTC),
                o[i], h[i], lo[i], c[i], v[i]) for i, d in enumerate(j)]


def _egaux(a, b):
    return np.array_equal(np.isnan(a), np.isnan(b)) and \
        np.allclose(a[~np.isnan(a)], b[~np.isnan(b)], rtol=1e-9, atol=1e-12)


def test_toutes_les_variables_sont_stationnaires_le_prix_non():
    from packages.ml.features import adf_stat
    from packages.ml.stationnaires import CRITERE_ADF, construire, diagnostic
    bars = _bars()
    diag = diagnostic(construire(bars))
    assert len(diag) >= 9
    echecs = {n: d["adf"] for n, d in diag.items() if not d["stationnaire"]}
    assert not echecs, echecs
    assert adf_stat(np.array([b.close for b in bars])) > CRITERE_ADF   # témoin


def test_aucune_fuite_temporelle():
    """Couper l'avenir ne change AUCUNE valeur passée, pour toutes les variables."""
    from packages.ml.stationnaires import construire
    bars = _bars(900)
    complet = construire(bars)
    for t in (250, 401, 677, 899):
        tronque = construire(bars[:t + 1])
        for n, x in complet.items():
            assert _egaux(x[:t + 1], tronque[n]), (n, t)


def test_invariance_d_echelle():
    """Un titre à 10 $ et le même à 1 000 $ donnent les mêmes variables."""
    from packages.ml.stationnaires import construire
    a = construire(_bars(700))
    b = construire(_bars(700, echelle=100.0, echelle_vol=1000.0))
    for n in a:
        assert _egaux(a[n], b[n]), n


def test_prechauffage_nan_puis_valeurs():
    from packages.ml.stationnaires import FENETRE_Z, construire
    f = construire(_bars(600))
    for n, x in f.items():
        assert np.isnan(x[0]), n
        assert np.isfinite(x[FENETRE_Z + 220:]).all(), n


def test_zscore_canal_plat_sans_division_par_zero():
    from packages.ml.stationnaires import zscore_glissant
    z = zscore_glissant(np.full(50, 7.0), 20)
    assert np.isnan(z).all()
    x = np.arange(30, dtype=float)
    assert zscore_glissant(x, 10)[-1] == pytest.approx((29 - 24.5) / np.std(x[-10:], ddof=1))


def test_registre_plugin_et_matrice():
    from packages.ml.stationnaires import construire, matrice, transformations
    assert "rsi_z" in transformations
    with pytest.raises(KeyError):
        construire(_bars(300), noms=["inconnue"])
    f = construire(_bars(400), noms=["rsi_z", "volume_z"])
    X, noms = matrice(f, [350, 399])
    assert X.shape == (2, 2) and noms == ["rsi_z", "volume_z"]


def test_diagnostic_serie_trop_courte_uncalibrated():
    from packages.ml.stationnaires import diagnostic
    d = diagnostic({"x": np.array([np.nan, 1.0, 2.0])})
    assert d["x"]["stationnaire"] is None
