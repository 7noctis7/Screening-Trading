"""Métriques de screening — vocabulaire commun aux FILTRES et au SCORING.

Une métrique renvoie `{symbol: valeur}` (NaN si indisponible). Deux sources unifiées :
1. le registre de facteurs du ranking (`momentum`, `trend`, `low_vol`, et
   `value`/`quality` si le module fondamental est chargé) — normalisables en z-score ;
2. des métriques prix internes, pour des filtres durs (liquidité, tendance,
   drawdown, volatilité, rendements). Point-in-time : on ne lit que les barres <= t.
"""

from __future__ import annotations

import contextlib
from collections.abc import Callable

import numpy as np

from packages.ranking.factors import FactorContext, factor_calcs

# Enregistre value/quality dans le registre s'ils sont dispo (deps fondamentales).
with contextlib.suppress(Exception):  # facteurs fondamentaux optionnels
    from packages.fundamentals import factors as _fund_factors  # noqa: F401


def _closes(bars: list, t: int) -> np.ndarray:
    return np.asarray([b.close for b in bars[: t + 1]], float)


def _vols(bars: list, t: int) -> np.ndarray:
    return np.asarray([b.volume for b in bars[: t + 1]], float)


def _ret(n: int) -> Callable[[np.ndarray, np.ndarray], float]:
    def f(c: np.ndarray, v: np.ndarray) -> float:
        return float(c[-1] / c[-1 - n] - 1.0) if c.size >= n + 1 else float("nan")
    return f


def _dist_sma(w: int) -> Callable[[np.ndarray, np.ndarray], float]:
    def f(c: np.ndarray, v: np.ndarray) -> float:
        return float(c[-1] / c[-w:].mean() - 1.0) if c.size >= w else float("nan")
    return f


def _above_sma(w: int) -> Callable[[np.ndarray, np.ndarray], float]:
    def f(c: np.ndarray, v: np.ndarray) -> float:
        if c.size < w:
            return float("nan")
        return 1.0 if c[-1] > c[-w:].mean() else 0.0
    return f


def _dollar_volume(c: np.ndarray, v: np.ndarray, w: int = 20) -> float:
    if c.size < 1 or v.size < 1:
        return float("nan")
    n = min(w, c.size, v.size)
    return float(np.mean(c[-n:] * v[-n:]))


def _drawdown_from_high(c: np.ndarray, v: np.ndarray, w: int = 252) -> float:
    if c.size < 2:
        return float("nan")
    peak = c[-min(w, c.size):].max()
    return float(c[-1] / peak - 1.0) if peak > 0 else float("nan")


def _ann_vol(w: int = 63) -> Callable[[np.ndarray, np.ndarray], float]:
    def f(c: np.ndarray, v: np.ndarray) -> float:
        if c.size < w + 1:
            return float("nan")
        r = np.diff(np.log(c[-w - 1:]))
        return float(r.std(ddof=1) * np.sqrt(252))
    return f


# Métriques prix : (close, volume) <= t -> float. Booléen 1.0/0.0 (filtrer via >=1).
PRICE_METRICS: dict[str, Callable[[np.ndarray, np.ndarray], float]] = {
    "last_close": lambda c, v: float(c[-1]) if c.size else float("nan"),
    "dollar_volume": _dollar_volume,
    "ret_1m": _ret(21),
    "ret_3m": _ret(63),
    "ret_6m": _ret(126),
    "ret_12m": _ret(252),
    "dist_sma50": _dist_sma(50),
    "dist_sma200": _dist_sma(200),
    "above_sma50": _above_sma(50),
    "above_sma200": _above_sma(200),
    "drawdown_from_high": _drawdown_from_high,
    "vol_63": _ann_vol(63),
}


def available_metrics() -> list[str]:
    """Liste des métriques utilisables (facteurs enregistrés + métriques prix)."""
    return sorted(set(factor_calcs.names()) | set(PRICE_METRICS))


def metric_values(name: str, ctx: FactorContext) -> dict[str, float]:
    """Résout une métrique : registre de facteurs d'abord, puis métriques prix.

    Lève `ValueError` si le nom est inconnu (échec franc, jamais silencieux).
    """
    if name in factor_calcs:
        return factor_calcs.create(name).values(ctx)
    fn = PRICE_METRICS.get(name)
    if fn is None:
        dispo = ", ".join(available_metrics())
        raise ValueError(f"métrique de screening inconnue : {name!r}. Dispo : {dispo}")
    out: dict[str, float] = {}
    for sym, bars in ctx.panel.items():
        t = min(ctx.t, len(bars) - 1)
        out[sym] = fn(_closes(bars, t), _vols(bars, t))
    return out
