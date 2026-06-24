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


def dedup_events(event_idx, min_gap: int = 0) -> list[int]:
    """Garde des events espacés d'au moins `min_gap` barres (collapse les grappes).

    Anti-autocorrélation : des fenêtres CAR qui se chevauchent (ex. 1 dépôt insider
    par semaine) ne sont PAS indépendantes → elles gonflent artificiellement le
    t-stat. On ne garde qu'un event par fenêtre. `min_gap=0` → aucun filtrage.
    """
    out: list[int] = []
    last = None
    for i in sorted(set(int(x) for x in event_idx)):
        if last is None or i - last >= min_gap:
            out.append(i)
            last = i
    return out


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


def aggregate_significance(series: dict, post: int = 5, n_sims: int = 1000,
                           seed: int = 0) -> dict:
    """Event-study CROSS-SECTIONNEL : CAR poolé sur tous les events + placebo.

    `series = {ticker: (returns, event_indices[, bench_returns])}`. Un seul ticker
    significatif ne prouve rien → on POOL. Si `bench_returns` est fourni, le CAR est
    ANORMAL (titre − benchmark) → on isole l'edge de la dérive de marché. Placebo :
    dates aléatoires par ticker (même nombre) puis pool → H0.
    """
    def _unpack(val):
        ret, idx = val[0], val[1]
        bench = val[2] if len(val) > 2 else None
        return ret, idx, bench

    cars: list[float] = []
    for val in series.values():
        ret, idx, bench = _unpack(val)
        cars.extend(c for i in idx if (c := car(ret, i, post, bench)) == c)
    if len(cars) < 5:
        return {"available": False}
    arr = np.array(cars)
    sd = float(arr.std(ddof=1))
    obs_mean = float(arr.mean())
    t = obs_mean / (sd / np.sqrt(len(arr))) if sd > 0 else 0.0
    rng = np.random.default_rng(seed)
    sims = np.empty(n_sims)
    for k in range(n_sims):
        pool: list[float] = []
        for val in series.values():
            ret, idx, bench = _unpack(val)
            n = len(np.asarray(ret, float))
            if n - post - 1 <= 0 or not idx:
                continue
            ridx = rng.integers(0, n - post - 1, size=len(idx))
            pool.extend(car(ret, int(j), post, bench) for j in ridx)
        sims[k] = float(np.mean(pool)) if pool else 0.0
    p = float((np.abs(sims) >= abs(obs_mean)).mean())
    return {"available": True, "n_assets": len(series), "n_events": len(arr),
            "mean_car": round(obs_mean, 5), "t_stat": round(float(t), 3),
            "placebo_p_value": round(p, 4), "significant": bool(p < 0.05)}
