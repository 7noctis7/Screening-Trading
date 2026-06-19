"""Cœur indiciel + satellite preset.

Mélange un ETF indiciel passif (le « cœur », ex. QQQ/Nasdaq 100) avec le preset actif (le
« satellite »). Objectif : capter le rendement de l'indice tout en conservant la gestion du
risque du preset (vol-targeting + DD-target), pour viser un meilleur couple rendement/risque
que l'un OU l'autre pris isolément.

On balaie la part « cœur » ∈ [0..1], on mesure les KPIs de chaque mélange, et on retient la
meilleure part par un objectif (Sharpe par défaut) — mais UNIQUEMENT si elle bat le preset pur
(core = 0). Sinon on reste à 100 % preset. Rééquilibrage quotidien (approximation légèrement
conservatrice : un peu de turnover en plus que mensuel). numpy pur, aucune dépendance.
"""

from __future__ import annotations

import numpy as np


def _stats(eq: list[float]) -> dict:
    """KPIs d'une courbe d'equity : CAGR, rendement total, Sharpe, Sortino, maxDD, Calmar."""
    e = np.asarray(eq, dtype=float)
    if e.size < 30:
        return {"available": False}
    r = e[1:] / e[:-1] - 1
    total = float(e[-1] / e[0] - 1)
    cagr = float((1 + total) ** (252.0 / len(r)) - 1) if total > -1 else -1.0
    sd = float(r.std())
    dn = r[r < 0]
    dsd = float((dn ** 2).mean() ** 0.5) if dn.size else 0.0
    peak = np.maximum.accumulate(e)
    mdd = float((e / peak - 1).min())
    return {"available": True, "cagr": round(cagr, 4), "total_return": round(total, 4),
            "sharpe": round(r.mean() / sd * (252 ** 0.5), 2) if sd > 0 else 0.0,
            "sortino": round(r.mean() / dsd * (252 ** 0.5), 2) if dsd > 0 else 0.0,
            "max_drawdown": round(mdd, 4),
            "calmar": round(cagr / abs(mdd), 2) if mdd < 0 else 0.0}


def blend_equity(preset_eq: list[float], index_closes: list[float], core_pct: float,
                 init_cap: float | None = None) -> tuple[list[float] | None, int]:
    """Courbe d'equity du mélange (core_pct × indice + (1-core_pct) × preset), rééq. quotidien.

    Aligne les deux séries sur leur QUEUE commune (les `n` derniers points). Renvoie
    (equity, n) où n = nombre de points de la courbe ; (None, 0) si échantillon insuffisant."""
    p = np.asarray(preset_eq, dtype=float)
    x = np.asarray(index_closes, dtype=float)
    n = min(p.size, x.size)
    if n < 31:
        return None, 0
    p, x = p[-n:], x[-n:]
    pr = p[1:] / p[:-1] - 1
    xr = x[1:] / x[:-1] - 1
    c = max(0.0, min(1.0, float(core_pct)))
    br = c * xr + (1.0 - c) * pr
    cap = float(init_cap) if init_cap is not None else float(p[0])
    eq = [cap]
    for rr in br:
        eq.append(eq[-1] * (1.0 + float(rr)))
    return [round(v, 2) for v in eq], len(eq)


def blend_equity_multi(preset_eq: list[float], cores: list[tuple[list[float], float]],
                       init_cap: float | None = None) -> tuple[list[float] | None, int]:
    """Mélange MULTI-CŒUR : equity = Σ wᵢ·cœurᵢ + (1-Σwᵢ)·preset, rééq. quotidien. `cores` est
    une liste de (série, poids). Aligne toutes les séries sur leur queue commune → (equity, n)."""
    series = [np.asarray(preset_eq, dtype=float)] + [np.asarray(c, dtype=float) for c, _ in cores]
    n = min(s.size for s in series)
    if n < 31:
        return None, 0
    series = [s[-n:] for s in series]
    rets = [s[1:] / s[:-1] - 1 for s in series]
    cw = [max(0.0, float(w)) for _, w in cores]
    pw = max(0.0, 1.0 - sum(cw))                       # part preset = reste
    weights = [pw] + cw
    br = np.zeros(n - 1)
    for w, r in zip(weights, rets):
        br = br + w * r
    cap = float(init_cap) if init_cap is not None else float(series[0][0])
    eq = [cap]
    for rr in br:
        eq.append(eq[-1] * (1.0 + float(rr)))
    return [round(v, 2) for v in eq], len(eq)


def optimize_index_core(preset_eq: list[float], index_closes: list[float],
                        grid: tuple[float, ...] = (0.0, 0.25, 0.5, 0.75, 1.0),
                        objective: str = "sharpe", min_improve: float = 0.01) -> dict:
    """Balaie la part « cœur », calcule les KPIs de chaque mélange et choisit la meilleure
    par `objective`. N'adopte un mélange (best_core > 0) QUE s'il bat le preset pur (core=0)
    d'au moins `min_improve` sur l'objectif. Renvoie best_core, table, improved, base/best_stats."""
    table = []
    for c in grid:
        eq, _ = blend_equity(preset_eq, index_closes, c)
        table.append({"core": round(float(c), 2),
                      "stats": _stats(eq) if eq else {"available": False}})
    base = next((row["stats"] for row in table if row["core"] == 0.0), {"available": False})
    valid = [row for row in table if row["stats"].get("available")]
    if not valid or not base.get("available"):
        return {"best_core": 0.0, "table": table, "improved": False,
                "base_stats": base, "best_stats": base, "objective": objective}
    best = max(valid, key=lambda row: row["stats"].get(objective, -1e9))
    base_obj = base.get(objective, -1e9)
    improved = best["core"] > 0.0 and best["stats"].get(objective, -1e9) > base_obj + min_improve
    return {"best_core": best["core"] if improved else 0.0,
            "best_stats": best["stats"] if improved else base,
            "table": table, "improved": improved, "base_stats": base, "objective": objective}
