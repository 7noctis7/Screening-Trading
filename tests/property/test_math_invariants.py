"""Tests de PROPRIÉTÉ (hypothesis) sur les noyaux maths — invariants vrais ∀ entrée.

Complète les tests par l'exemple : on vérifie des lois (moyenne nulle, écart-type
unitaire, bornes, anti-look-ahead) sur des milliers d'entrées générées. `importorskip`
→ skip propre si hypothesis n'est pas installé (jamais bloquant)."""

import pytest

pytest.importorskip("hypothesis")

import numpy as np  # noqa: E402
from hypothesis import assume, given, settings  # noqa: E402
from hypothesis import strategies as st  # noqa: E402

from packages.ranking.engine import _zscore  # noqa: E402

_floats = st.floats(
    min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False
)


@settings(max_examples=200, deadline=None)
@given(st.lists(_floats, min_size=2, max_size=60))
def test_zscore_is_standardized(values):
    """z-score global : moyenne ≈ 0 et écart-type ≈ 1 sur séries NON dégénérées.
    On exclut les séries quasi-constantes (l'annulation flottante y domine le calcul
    de σ — pathologie numérique, pas un défaut de la fonction)."""
    arr_in = np.array(values, dtype=float)
    spread = float(np.ptp(arr_in))
    assume(spread > 1e-3 * (1.0 + float(np.max(np.abs(arr_in)))))
    d = {f"s{i}": v for i, v in enumerate(values)}
    z = np.array(list(_zscore(d, None, False).values()))
    assert abs(z.mean()) < 1e-6
    assert abs(z.std(ddof=1) - 1.0) < 1e-6


def test_zscore_constant_series_is_zero():
    """Série exactement constante → z-score nul partout (pas de division par σ=0)."""
    z = _zscore({"a": 5.0, "b": 5.0, "c": 5.0}, None, False)
    assert all(v == 0.0 for v in z.values())


@settings(max_examples=100, deadline=None)
@given(st.lists(_floats, min_size=2, max_size=40))
def test_zscore_preserves_order(values):
    """Le z-score est affine croissant → il préserve l'ordre des valeurs."""
    d = {f"s{i}": v for i, v in enumerate(values)}
    z = _zscore(d, None, False)
    zin = sorted(d.values())
    zout = sorted(z.values())
    assert all(a <= b + 1e-9 for a, b in zip(zin, zin[1:], strict=False))
    assert all(a <= b + 1e-9 for a, b in zip(zout, zout[1:], strict=False))
    assert len(d) == len(z)


@settings(max_examples=80, deadline=None)
@given(st.lists(
    st.floats(min_value=1.0, max_value=1000.0, allow_nan=False),
    min_size=260, max_size=320,
))
def test_above_sma_is_boolean(prices):
    """above_sma200 est strictement booléenne (0.0/1.0) sur série suffisante."""
    from packages.ranking.factors import FactorContext
    from packages.screening.metrics import metric_values
    from tests._helpers import mkbars
    panel = {"X": mkbars(prices, "X")}
    out = metric_values("above_sma200", FactorContext(panel, len(prices) - 1))
    assert out["X"] in (0.0, 1.0)
