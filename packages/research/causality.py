"""Tests de causalité pour données alternatives — Granger + information mutuelle.

Une série exogène (exportations de Taïwan, gas burn Ethereum, spread SOFR-OIS, commits
GitHub) n'entre dans le screener qu'après avoir prouvé DEUX choses :
  1. elle apporte de l'information sur le rendement futur (et pas l'inverse) ;
  2. elle l'apporte à un horizon compatible avec sa latence de publication.

Deux tests complémentaires, volontairement différents :
  - **Granger** : linéaire, dirigé, avec p-value — le juge de paix. Teste si les retards de
    x réduisent l'erreur de prévision de y au-delà des retards de y seuls.
  - **Information mutuelle** : non paramétrique, capte les dépendances non linéaires (un
    seuil, une saturation, un effet en U) que Granger rate — mais non dirigée et biaisée
    en petit échantillon, d'où la correction de Miller-Madow et le test par permutation.

⚠️ Pièges encodés ici :
  - Granger sur des séries NON STATIONNAIRES produit des rejets fantaisistes : travailler
    en rendements/différences, jamais en niveaux (`difference=True` par défaut).
  - Une causalité de Granger n'est PAS une causalité : c'est de la précédence prédictive.
  - Multiple testing : k sources × h horizons = k·h essais. Corriger, ou tout « trouver ».
  - Latence de publication : tester x(t) contre r(t+1) alors que x(t) n'est publié qu'en
    t+3 est la fuite la plus banale de l'alt-data. `pit_align` l'interdit.

stdlib + numpy.
"""

from __future__ import annotations

import math

import numpy as np

_FPMIN, _EPS, _MAXIT = 1e-300, 3e-16, 300


def _betacf(a: float, b: float, x: float) -> float:
    """Fraction continue de Lentz pour la bêta incomplète (Numerical Recipes)."""
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    d = _FPMIN if abs(d) < _FPMIN else d
    d = 1.0 / d
    h = d
    for m in range(1, _MAXIT + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        d = _FPMIN if abs(d) < _FPMIN else d
        c = 1.0 + aa / c
        c = _FPMIN if abs(c) < _FPMIN else c
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        d = _FPMIN if abs(d) < _FPMIN else d
        c = 1.0 + aa / c
        c = _FPMIN if abs(c) < _FPMIN else c
        d = 1.0 / d
        de = d * c
        h *= de
        if abs(de - 1.0) < _EPS:
            break
    return h


def betainc(a: float, b: float, x: float) -> float:
    """Bêta incomplète régularisée I_x(a, b) — base des p-values F et t."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    lb = (math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
          + a * math.log(x) + b * math.log1p(-x))
    if x < (a + 1.0) / (a + b + 2.0):
        return math.exp(lb) * _betacf(a, b, x) / a
    return 1.0 - math.exp(lb) * _betacf(b, a, 1.0 - x) / b


def f_pvalue(f: float, df1: int, df2: int) -> float:
    """P(F > f) pour une loi de Fisher(df1, df2)."""
    if f <= 0 or df1 <= 0 or df2 <= 0:
        return 1.0
    return float(betainc(df2 / 2.0, df1 / 2.0, df2 / (df2 + df1 * f)))


def _ols_rss(X: np.ndarray, y: np.ndarray) -> float:
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    r = y - X @ beta
    return float(r @ r)


def granger_causality(y, x, lags: int = 3, difference: bool = True) -> dict:
    """x cause-t-il y au sens de Granger ? Test F du modèle contraint vs non contraint.

      contraint     : y_t = c + somme_i a_i·y_(t−i)
      non contraint : y_t = c + somme_i a_i·y_(t−i) + somme_i b_i·x_(t−i)
      F = ((RSS_c − RSS_nc)/p) / (RSS_nc/(n − 2p − 1))
    """
    Y = np.asarray(y, dtype=float)
    X = np.asarray(x, dtype=float)
    m = min(Y.size, X.size)
    Y, X = Y[-m:], X[-m:]
    if difference:
        Y, X = np.diff(Y), np.diff(X)
    p = max(1, int(lags))
    n = Y.size - p
    if n < 3 * p + 5:
        return {"available": False, "status": "UNCALIBRATED", "n": int(max(0, n)),
                "hint": f"il faut au moins {3 * p + 5} observations après retards"}
    target = Y[p:]
    cols_y = [Y[p - i:-i] for i in range(1, p + 1)]
    cols_x = [X[p - i:-i] for i in range(1, p + 1)]
    ones = np.ones(n)
    Xr = np.column_stack([ones, *cols_y])
    Xu = np.column_stack([ones, *cols_y, *cols_x])
    rss_r, rss_u = _ols_rss(Xr, target), _ols_rss(Xu, target)
    df2 = n - (2 * p + 1)
    if rss_u <= 0 or df2 <= 0:
        return {"available": False, "status": "UNCALIBRATED", "n": int(n)}
    f = ((rss_r - rss_u) / p) / (rss_u / df2)
    pv = f_pvalue(f, p, df2)
    return {"available": True, "f_stat": round(float(f), 4), "p_value": round(pv, 6),
            "lags": p, "n": int(n), "df": (p, int(df2)),
            "r2_gain": round(float(max(0.0, (rss_r - rss_u) / rss_r)), 5),
            "causal": bool(pv < 0.05)}


def granger_both_ways(y, x, lags: int = 3, difference: bool = True) -> dict:
    """Teste les deux sens. Une source d'alt-data utile prédit le marché, pas l'inverse."""
    fwd = granger_causality(y, x, lags, difference)
    rev = granger_causality(x, y, lags, difference)
    if not (fwd.get("available") and rev.get("available")):
        return {"available": False, "status": "UNCALIBRATED"}
    usable = bool(fwd["causal"] and not rev["causal"])
    return {"available": True, "x_causes_y": fwd, "y_causes_x": rev,
            "usable_as_predictor": usable,
            "note": ("" if usable else
                     "soit x ne prédit pas y, soit la relation est bidirectionnelle "
                     "(le marché anticipe la donnée : aucune avance exploitable)")}


def mutual_information(x, y, bins: int = 8, correct_bias: bool = True) -> dict:
    """Information mutuelle par histogramme, avec correction de biais Miller-Madow.

    L'IM plug-in est POSITIVEMENT biaisée : sur du bruit pur elle vaut ~(mx·my)/(2n) > 0.
    Sans correction ni test par permutation, elle « trouve » toujours quelque chose.
    """
    a = np.asarray(x, dtype=float)
    b = np.asarray(y, dtype=float)
    m = min(a.size, b.size)
    a, b = a[-m:], b[-m:]
    ok = np.isfinite(a) & np.isfinite(b)
    a, b = a[ok], b[ok]
    n = a.size
    if n < 30:
        return {"available": False, "status": "UNCALIBRATED", "n": int(n)}
    H, _, _ = np.histogram2d(a, b, bins=bins)
    pxy = H / n
    px, py = pxy.sum(axis=1, keepdims=True), pxy.sum(axis=0, keepdims=True)
    nz = pxy > 0
    mi = float((pxy[nz] * np.log(pxy[nz] / (px @ py)[nz])).sum())
    if correct_bias:
        mx, my, mxy = int((px > 0).sum()), int((py > 0).sum()), int(nz.sum())
        mi += (mx + my - mxy - 1) / (2.0 * n)
    return {"available": True, "mi": round(max(0.0, mi), 6), "n": int(n), "bins": bins,
            "mi_normalized": round(max(0.0, mi) / math.log(bins), 4)}


def mi_permutation_test(x, y, bins: int = 8, n_perm: int = 200, seed: int = 0) -> dict:
    """p-value de l'information mutuelle par permutation — le seul seuil honnête."""
    base = mutual_information(x, y, bins)
    if not base.get("available"):
        return base
    rng = np.random.default_rng(seed)
    b = np.asarray(y, dtype=float)[-base["n"]:].copy()
    null = []
    for _ in range(max(20, n_perm)):
        rng.shuffle(b)
        r = mutual_information(x, b, bins)
        null.append(r["mi"] if r.get("available") else 0.0)
    arr = np.asarray(null)
    pv = float((1 + (arr >= base["mi"]).sum()) / (1 + arr.size))
    return {**base, "p_value": round(pv, 5), "null_mean": round(float(arr.mean()), 6),
            "significant": bool(pv < 0.05)}


def pit_align(obs_dates, values, publication_lag_days: float) -> list[dict]:
    """Attribue à chaque observation son TEMPS DE CONNAISSANCE = date + latence.

    Toute étude qui compare x(t) au rendement de t à t+1 sans appliquer cette latence
    mesure une information dont personne ne disposait. Renvoie des enregistrements prêts
    pour `packages/common/pit_guard.pit_filter`.
    """
    from datetime import timedelta
    lag = timedelta(days=float(publication_lag_days))
    return [{"obs_date": d, "realtime_start": d + lag, "value": float(v)}
            for d, v in zip(obs_dates, values)]


def sidak_level(alpha: float, n_tests: int) -> float:
    """Seuil individuel corrigé pour k sources × h horizons d'essais."""
    n = max(1, int(n_tests))
    return float(1.0 - (1.0 - alpha) ** (1.0 / n))
