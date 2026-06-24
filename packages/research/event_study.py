"""Event-study — rendements anormaux cumulés (CAR) autour d'events + test placebo.

Dit si un lien event→prix EXISTE *avant* tout ML/LLM. CAR sur la fenêtre POST-event
(anti look-ahead). Le placebo rejoue le CAR sur des dates ALÉATOIRES (H0) → p-value
empirique : si l'effet réel ≈ placebo, c'est du bruit. Pur numpy.
"""

from __future__ import annotations

from bisect import bisect_left

import numpy as np


def event_indices(bar_dates, event_dates) -> list[int]:
    """Dates d'event → indice de la 1re barre à/après (barre tradable).

    `bar_dates` trié croissant. Dédup + trié. Anti look-ahead : on entre à la barre
    qui SUIT l'event public, jamais avant.
    """
    bd = [str(d) for d in bar_dates]
    out: list[int] = []
    for e in event_dates:
        i = bisect_left(bd, str(e))
        if i < len(bd):
            out.append(i)
    return sorted(set(out))


def _abnormal(asset_ret: np.ndarray, bench_ret: np.ndarray | None) -> np.ndarray:
    a = np.asarray(asset_ret, float)
    b = np.zeros_like(a) if bench_ret is None else np.asarray(bench_ret, float)
    return a - b


def car(asset_ret, event_idx: int, post: int = 5,
        bench_ret=None) -> float:
    """Rendement anormal cumulé sur (event_idx, event_idx+post]. NaN si hors borne."""
    ar = _abnormal(asset_ret, bench_ret)
    j0 = event_idx + 1
    if j0 >= len(ar):
        return float("nan")
    return float(ar[j0: min(len(ar), j0 + post)].sum())


def event_study(asset_ret, event_indices, post: int = 5, bench_ret=None) -> dict:
    """CAR moyen + t-stat. `available=False` si trop peu d'events."""
    cars = [c for i in event_indices if (c := car(asset_ret, i, post, bench_ret)) == c]
    if len(cars) < 2:
        return {"available": False}
    arr = np.array(cars)
    sd = float(arr.std(ddof=1))
    t = float(arr.mean() / (sd / np.sqrt(len(arr)))) if sd > 0 else 0.0
    return {"available": True, "n": len(arr), "mean_car": round(float(arr.mean()), 5),
            "t_stat": round(t, 3)}


def placebo_pvalue(asset_ret, n_events: int, mean_car: float, post: int = 5,
                   bench_ret=None, n_sims: int = 1000, seed: int = 0) -> float:
    """p-value empirique bilatérale (|CAR| placebo ≥ |observé|)."""
    rng = np.random.default_rng(seed)
    n = len(np.asarray(asset_ret, float))
    if n - post - 2 <= 0:
        return 1.0
    sims = np.empty(n_sims)
    for k in range(n_sims):
        idx = rng.integers(0, n - post - 1, size=n_events)
        sims[k] = np.mean([car(asset_ret, int(i), post, bench_ret) for i in idx])
    return float((np.abs(sims) >= abs(mean_car)).mean())


def significance(asset_ret, event_indices, post: int = 5, bench_ret=None,
                 n_sims: int = 1000, seed: int = 0) -> dict:
    """Event-study + placebo → `significant` (p<0.05). Le gate AVANT ML."""
    obs = event_study(asset_ret, event_indices, post, bench_ret)
    if not obs.get("available"):
        return obs
    p = placebo_pvalue(asset_ret, len(event_indices), obs["mean_car"], post,
                       bench_ret, n_sims, seed)
    return {**obs, "placebo_p_value": round(p, 4), "significant": bool(p < 0.05)}
