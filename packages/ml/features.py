"""Différenciation fractionnaire + assemblage de features point-in-time.

Frac-diff (López de Prado, AFML ch. 5) : rend une série stationnaire en gardant un
MAXIMUM de mémoire (vs la diff entière qui détruit l'information de niveau). `d` réel ∈ [0,1].

FeatureBuilder : assemble une matrice X alignée sur les temps d'entrée, en lisant les
features techniques (feature store, à la barre) et macro (`as_of`, point-in-time). Aucune
valeur future ne peut entrer → pas de fuite (cohérent avec le reste du système).
"""

from __future__ import annotations

from datetime import datetime

import numpy as np


def fracdiff_weights(d: float, thresh: float = 1e-4) -> np.ndarray:
    """Poids de la fenêtre fixe pour la diff fractionnaire (tronqués à `thresh`)."""
    w = [1.0]
    k = 1
    while True:
        w_k = -w[-1] * (d - k + 1) / k
        if abs(w_k) < thresh:
            break
        w.append(w_k)
        k += 1
    return np.array(w[::-1])


def frac_diff(series: np.ndarray, d: float = 0.4, thresh: float = 1e-4) -> np.ndarray:
    """Série fractionnairement différenciée (NaN sur la fenêtre de warm-up)."""
    w = fracdiff_weights(d, thresh)
    width = len(w)
    out = np.full(len(series), np.nan)
    for i in range(width - 1, len(series)):
        out[i] = np.dot(w, series[i - width + 1: i + 1])
    return out


def adf_stat(series: np.ndarray, lag: int = 1) -> float:
    """Statistique ADF (Augmented Dickey-Fuller) avec constante — OLS pur numpy.

    H0 : racine unitaire (non stationnaire). Stat très négative → rejette H0.
    Seuil usuel ≈ -2,86 (5 %, constante). NaN si trop peu de points.
    """
    y = np.asarray(series, float)
    y = y[np.isfinite(y)]
    m = y.size - 1
    if m - lag < 8:
        return float("nan")
    dy = np.diff(y)
    cols = [np.ones(m - lag), y[lag:m]]                 # constante + niveau y_{t-1}
    for i in range(1, lag + 1):
        cols.append(dy[lag - i: m - i])                # lags de Δy
    x = np.column_stack(cols)
    yv = dy[lag:]
    beta, _, _, _ = np.linalg.lstsq(x, yv, rcond=None)
    resid = yv - x @ beta
    dof = x.shape[0] - x.shape[1]
    if dof <= 0:
        return float("nan")
    sigma2 = float(resid @ resid) / dof
    try:
        se = float(np.sqrt(sigma2 * np.linalg.inv(x.T @ x)[1, 1]))
    except np.linalg.LinAlgError:
        return float("nan")
    return float(beta[1] / se) if se > 0 else float("nan")


def min_ffd(series: np.ndarray, crit: float = -2.86,
            ds: tuple[float, ...] | None = None, thresh: float = 1e-4) -> dict:
    """Minimum FFD (López de Prado) : plus PETIT `d` ∈ [0,1] stationnarisant la série
    (ADF < `crit`) → différenciation minimale → mémoire maximale préservée.

    Renvoie `{d, adf, stationary}`. Aucun `d` ne passe → `d=1.0` (diff entière).
    """
    grid = ds if ds is not None else tuple(i / 10 for i in range(11))
    arr = np.asarray(series, float)
    last = {"d": 1.0, "adf": None, "stationary": False}
    for d in grid:
        fd = frac_diff(arr, d=d, thresh=thresh)
        stat = adf_stat(fd)
        ok = stat == stat and stat < crit
        last = {"d": round(d, 2), "adf": round(stat, 3) if stat == stat else None,
                "stationary": bool(ok)}
        if ok:
            return last
    return last


class FeatureBuilder:
    """Construit X point-in-time : technique (feature store) + macro (`as_of`)."""

    def __init__(self, feature_store, macro_store=None,
                 macro_series: tuple[str, ...] = ()) -> None:
        self.fs = feature_store
        self.ms = macro_store
        self.macro_series = macro_series

    def build(self, symbol: str, timeframe: str,
              entry_times: list[datetime]) -> tuple[np.ndarray, list[str]]:
        tech_names = self.fs.feature_names(symbol, timeframe)
        tech = {name: dict(self.fs.read(symbol, timeframe, name)) for name in tech_names}
        names = list(tech_names) + [f"macro_{s}" for s in self.macro_series]
        rows = []
        for t in entry_times:
            row = [tech[name].get(t, np.nan) for name in tech_names]
            for s in self.macro_series:
                r = self.ms.as_of(s, t) if self.ms else None
                row.append(r[1] if r else np.nan)
            rows.append(row)
        return np.array(rows, dtype=float), names
