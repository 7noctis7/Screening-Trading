"""Event-study FUNDING (mean-reversion) — un funding extrême précède-t-il un retour ?

On FADE le positionnement : funding très positif (longs sur-tendus) → on SHORT ;
très négatif → on LONG. direction = −signe(z-score du funding). z-score CAUSAL (fenêtre
passée uniquement → anti look-ahead). CAR signé sur la fenêtre post + placebo (dates
aléatoires) = H0. Si l'effet réel ≈ placebo, c'est du bruit. numpy.
"""

from __future__ import annotations

import numpy as np


def zscore_causal(x, window: int = 30) -> np.ndarray:
    """z-score à t sur les `window` valeurs PASSÉES (≤ t-1). 0 si indisponible."""
    a = np.asarray(x, float)
    z = np.zeros_like(a)
    for t in range(len(a)):
        lo = max(0, t - window)
        past = a[lo:t]
        if past.size >= 5:
            sd = past.std(ddof=1)
            if sd > 0:
                z[t] = (a[t] - past.mean()) / sd
    return z


def fade_events(fund_z, threshold: float = 1.5):
    """[(idx, direction)] où |z|>threshold ; direction = −signe(z) (fade)."""
    z = np.asarray(fund_z, float)
    return [(i, -1.0 if z[i] > 0 else 1.0)
            for i in range(len(z)) if abs(z[i]) > threshold]


def fade_car(rets, idx: int, direction: float, post: int = 5) -> float:
    """Rendement cumulé SIGNÉ (direction × forward) sur (idx, idx+post]. nan si hors."""
    r = np.asarray(rets, float)
    j0 = idx + 1
    if j0 >= len(r):
        return float("nan")
    return float(direction * r[j0: min(len(r), j0 + post)].sum())


def significance(rets, fund_z, post: int = 5, threshold: float = 1.5,
                 n_sims: int = 1000, seed: int = 0) -> dict:
    """CAR signé moyen des events extrêmes + placebo → `significant` (p<0.05)."""
    rets = np.asarray(rets, float)
    z = np.asarray(fund_z, float)
    events = fade_events(z, threshold)
    cars = [c for i, d in events if (c := fade_car(rets, i, d, post)) == c]
    if len(cars) < 5:
        return {"available": False, "n": len(cars)}
    arr = np.array(cars)
    mean = float(arr.mean())
    sd = float(arr.std(ddof=1))
    t = mean / (sd / np.sqrt(len(arr))) if sd > 0 else 0.0
    rng = np.random.default_rng(seed)
    n = len(rets)
    sims = np.empty(n_sims)
    for k in range(n_sims):
        ridx = rng.integers(0, max(1, n - post - 1), size=len(cars))
        # même logique fade : direction = −signe(z) à la date aléatoire
        sims[k] = float(np.mean([fade_car(rets, int(i),
                                          -1.0 if z[i] > 0 else 1.0, post)
                                 for i in ridx]))
    p = float((np.abs(sims) >= abs(mean)).mean())
    return {"available": True, "n": len(arr), "mean_car": round(mean, 5),
            "t_stat": round(t, 3), "placebo_p_value": round(p, 4),
            "significant": bool(p < 0.05)}


def aggregate_significance(series: dict, post: int = 5, threshold: float = 1.5,
                           n_sims: int = 1000, seed: int = 0) -> dict:
    """Pool CROSS-ACTIF du fade funding. `series = {sym: (rets, fund_z)}`."""
    cars: list[float] = []
    for rets, z in series.values():
        z = np.asarray(z, float)
        rets = np.asarray(rets, float)
        cars.extend(c for i, d in fade_events(z, threshold)
                    if (c := fade_car(rets, i, d, post)) == c)
    if len(cars) < 5:
        return {"available": False, "n_events": len(cars)}
    arr = np.array(cars)
    mean, sd = float(arr.mean()), float(arr.std(ddof=1))
    t = mean / (sd / np.sqrt(len(arr))) if sd > 0 else 0.0
    rng = np.random.default_rng(seed)
    sims = np.empty(n_sims)
    for k in range(n_sims):
        pool: list[float] = []
        for rets, z in series.values():
            z = np.asarray(z, float)
            rets = np.asarray(rets, float)
            n = len(rets)
            n_ev = len(fade_events(z, threshold))
            if n - post - 1 <= 0 or n_ev == 0:
                continue
            ridx = rng.integers(0, n - post - 1, size=n_ev)
            pool.extend(fade_car(rets, int(i), -1.0 if z[i] > 0 else 1.0, post)
                        for i in ridx)
        sims[k] = float(np.mean(pool)) if pool else 0.0
    p = float((np.abs(sims) >= abs(mean)).mean())
    return {"available": True, "n_assets": len(series), "n_events": len(arr),
            "mean_car": round(mean, 5), "t_stat": round(t, 3),
            "placebo_p_value": round(p, 4), "significant": bool(p < 0.05)}
