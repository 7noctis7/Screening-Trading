"""Exposant de Hurst par analyse à plage rescalée (R/S) — tendance ou retour à la moyenne ?

Question opérationnelle : sur CET actif, à CETTE échelle, faut-il déployer du momentum ou de
l'arbitrage statistique ? L'exposant de Hurst y répond en mesurant la persistance des
rendements.

    E[ R(n)/S(n) ] = C · n^H

R(n) = étendue des écarts CUMULÉS à la moyenne sur une fenêtre de n points ;
S(n) = écart-type de la fenêtre. La pente de log(R/S) sur log(n) estime H.

⚠️ Deux pièges qui rendent la plupart des implémentations retail inutilisables :

1. **Le R/S brut est biaisé vers le haut sur fenêtres courtes.** Une marche aléatoire pure
   sort à H ≈ 0,6 et l'on conclut « tendance » sur du bruit. On corrige par l'espérance
   d'Anis-Lloyd sous H = 0,5 : `H = 0,5 + pente( log(R/S observé) − log(E[R/S]) )`.
2. **Aucun H n'est significatif sans distribution nulle.** On la construit par permutation
   des rendements (détruit la mémoire, conserve la distribution) : hors de la bande, on
   classe ; dedans, on ne classe pas — on coupe l'allocation.

Classification (seulement si H sort de la bande nulle) :
  H < 0,5 anti-persistant  → retour à la moyenne / arbitrage statistique
  H > 0,5 persistant       → suivi de tendance / momentum
  sinon                    → marche aléatoire : aucune des deux familles n'a d'edge ici

numpy pur, testable hors-ligne. S'applique aux RENDEMENTS, jamais aux prix bruts.
"""

from __future__ import annotations

import math

import numpy as np


def _expected_rs(n: int) -> float:
    """E[R/S] d'une série sans mémoire (Anis-Lloyd, corrigé Peters) — la référence H = 0,5."""
    if n < 2:
        return float("nan")
    k = np.arange(1, n)
    somme = float(np.sum(np.sqrt((n - k) / k)))
    if n > 340:
        front = (n - 0.5) / n * (n * math.pi / 2.0) ** -0.5
    else:
        front = ((n - 0.5) / n
                 * math.gamma((n - 1) / 2.0) / (math.sqrt(math.pi) * math.gamma(n / 2.0)))
    return float(front * somme)


def _rs_mean(x: np.ndarray, n: int) -> float | None:
    """R/S moyen sur les blocs NON CHEVAUCHANTS de taille n (chevaucher gonfle la stabilité)."""
    m = x.size // n
    if m < 1:
        return None
    vals = []
    for i in range(m):
        w = x[i * n:(i + 1) * n]
        s = float(w.std(ddof=1))
        if s <= 0:
            continue
        dev = np.cumsum(w - w.mean())
        r = float(dev.max() - dev.min())
        if r > 0:
            vals.append(r / s)
    return float(np.mean(vals)) if vals else None


def _window_sizes(n_obs: int, min_n: int = 10, n_points: int = 12) -> list[int]:
    """Tailles de fenêtre en progression géométrique — l'ajustement est en log-log."""
    hi = max(min_n * 2, n_obs // 4)
    if hi <= min_n:
        return []
    grid = np.unique(np.round(np.geomspace(min_n, hi, n_points)).astype(int))
    return [int(v) for v in grid if v >= min_n]


def hurst_rs(returns, min_n: int = 10, corrected: bool = True) -> dict:
    """Exposant de Hurst par R/S. `corrected=True` retire le biais de petit échantillon."""
    x = np.asarray(returns, dtype=float)
    x = x[np.isfinite(x)]
    if x.size < 64:
        return {"available": False, "status": "UNCALIBRATED", "n": int(x.size),
                "hint": "≥ 64 rendements requis pour un R/S interprétable"}
    ns, ys, es = [], [], []
    for n in _window_sizes(x.size, min_n):
        rs = _rs_mean(x, n)
        if rs is None or rs <= 0:
            continue
        ns.append(n)
        ys.append(math.log(rs))
        es.append(math.log(_expected_rs(n)))
    if len(ns) < 4:
        return {"available": False, "status": "UNCALIBRATED", "n": int(x.size)}
    lx = np.log(np.asarray(ns, dtype=float))
    A = np.column_stack([np.ones(lx.size), lx])

    def _fit(vec):
        b, *_ = np.linalg.lstsq(A, vec, rcond=None)
        res = vec - A @ b
        tot = float(((vec - vec.mean()) ** 2).sum())
        return float(b[1]), (1.0 - float((res ** 2).sum()) / tot if tot > 0 else 0.0)

    y_brut = np.asarray(ys)
    pente_brute, r2 = _fit(y_brut)          # R² = tenue de la LOI DE PUISSANCE (données brutes)
    if corrected:                            # la correction ne déplace que la PENTE, pas le R²
        pente, _ = _fit(y_brut - np.asarray(es))
        h = 0.5 + pente
    else:
        h = pente_brute
    return {"available": True, "hurst": round(float(np.clip(h, 0.0, 1.0)), 4),
            "corrected": corrected, "r2": round(r2, 4), "n": int(x.size),
            "n_windows": len(ns), "window_min": ns[0], "window_max": ns[-1]}


def hurst_significance(returns, n_perm: int = 200, seed: int = 0,
                       min_n: int = 10) -> dict:
    """Bande nulle par PERMUTATION : la mémoire est détruite, la distribution conservée.

    C'est le seul seuil honnête. Un H de 0,55 sur 200 points n'est pas distinguable de 0,5.
    """
    base = hurst_rs(returns, min_n=min_n)
    if not base.get("available"):
        return base
    x = np.asarray(returns, dtype=float)
    x = x[np.isfinite(x)].copy()
    rng = np.random.default_rng(seed)
    null = []
    for _ in range(max(30, n_perm)):
        rng.shuffle(x)
        r = hurst_rs(x, min_n=min_n)
        if r.get("available"):
            null.append(r["hurst"])
    if len(null) < 20:
        return {**base, "significant": False, "status": "UNCALIBRATED"}
    arr = np.asarray(null)
    lo, hi = (float(np.quantile(arr, 0.025)), float(np.quantile(arr, 0.975)))
    h = base["hurst"]
    p = float((1 + np.sum(np.abs(arr - arr.mean()) >= abs(h - arr.mean()))) / (1 + arr.size))
    return {**base, "null_lo": round(lo, 4), "null_hi": round(hi, 4),
            "null_mean": round(float(arr.mean()), 4), "p_value": round(p, 5),
            "significant": bool(h < lo or h > hi)}


def regime_from_hurst(returns, n_perm: int = 200, seed: int = 0) -> dict:
    """Verdict opérationnel : quelle FAMILLE de stratégie a le droit d'être déployée ici."""
    r = hurst_significance(returns, n_perm=n_perm, seed=seed)
    if not r.get("available"):
        return {"available": False, "status": r.get("status", "UNCALIBRATED"),
                "regime": "inconnu", "action": "aucune allocation"}
    if not r.get("significant"):
        return {**r, "regime": "marche_aleatoire",
                "action": "aucune allocation — ni momentum ni retour à la moyenne",
                "note": f"H={r['hurst']} dans la bande nulle "
                        f"[{r.get('null_lo')}, {r.get('null_hi')}]"}
    if r["hurst"] > 0.5:
        return {**r, "regime": "persistant", "action": "suivi de tendance / momentum"}
    return {**r, "regime": "anti_persistant",
            "action": "retour à la moyenne / arbitrage statistique"}


def rolling_hurst(returns, window: int = 252, step: int = 21, min_n: int = 10) -> dict:
    """H sur fenêtre GLISSANTE (causale : chaque point n'utilise que son propre passé)."""
    x = np.asarray(returns, dtype=float)
    x = x[np.isfinite(x)]
    if x.size < window:
        return {"available": False, "status": "UNCALIBRATED", "n": int(x.size)}
    idx, vals = [], []
    for end in range(window, x.size + 1, max(1, step)):
        r = hurst_rs(x[end - window:end], min_n=min_n)
        if r.get("available"):
            idx.append(end - 1)
            vals.append(r["hurst"])
    if not vals:
        return {"available": False, "status": "UNCALIBRATED"}
    return {"available": True, "index": idx, "hurst": vals,
            "last": vals[-1], "median": round(float(np.median(vals)), 4),
            "instable": bool(float(np.std(vals)) > 0.10)}
