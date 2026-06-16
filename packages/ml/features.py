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
