"""Portefeuille à volatilité gérée (Moreira & Muir, *Volatility-Managed Portfolios*, JF 2017).

Principe : l'exposition à t est inversement proportionnelle à la **volatilité réalisée récente**
(connue à t−1 → aucune fuite du futur) : on baisse la voile quand le marché s'agite, on la remonte
quand il se calme. La vol étant persistante (clustering) et anti-corrélée au rendement, cela
**réduit les drawdowns** et, via le *volatility drag* (CAGR ≈ μ − σ²/2), améliore souvent le
**rendement composé net**. numpy pur, point-in-time, testable.
"""

from __future__ import annotations

import numpy as np


def realized_vol(returns, window: int = 20) -> np.ndarray:
    """Volatilité annualisée glissante (fenêtre `window`), NaN tant que l'historique est trop court."""
    r = np.asarray(returns, dtype=float)
    out = np.full(len(r), np.nan)
    for i in range(len(r)):
        lo = max(0, i - window + 1)
        if i - lo + 1 >= max(5, window // 2):
            out[i] = float(r[lo:i + 1].std()) * np.sqrt(252)
    return out


def _stats(rets: np.ndarray) -> dict:
    r = np.asarray(rets, dtype=float)
    r = r[~np.isnan(r)]
    if r.size < 5:
        return {"available": False}
    eq = np.cumprod(1 + r)
    total = float(eq[-1] - 1)
    cagr = float((1 + total) ** (252.0 / r.size) - 1) if total > -1 else -1.0
    sd = float(r.std())
    vol = sd * np.sqrt(252)
    sharpe = float(r.mean() / sd * np.sqrt(252)) if sd > 0 else 0.0
    peak = np.maximum.accumulate(eq)
    mdd = float((eq / peak - 1).min())
    return {"available": True, "total_return": round(total, 4), "cagr": round(cagr, 4),
            "vol": round(vol, 4), "sharpe": round(sharpe, 2), "max_drawdown": round(mdd, 4)}


def volatility_managed(returns, target_vol: float = 0.15, window: int = 20,
                       max_leverage: float = 1.0, floor_vol: float = 0.02) -> dict:
    """Rendements ré-échelonnés par `target_vol / vol_réalisée(t−1)`, exposition plafonnée.

    max_leverage=1.0 → jamais de levier (exposition ∈ [0, 1]). floor_vol évite la division par ~0.
    """
    r = np.asarray(returns, dtype=float)
    rv = realized_vol(r, window)
    expo = np.zeros(len(r))
    scaled = np.zeros(len(r))
    for i in range(len(r)):
        v = rv[i - 1] if i > 0 and not np.isnan(rv[i - 1]) else np.nan   # vol connue à t−1 (anti-fuite)
        e = 0.0 if (np.isnan(v) or v < floor_vol) else min(max_leverage, target_vol / v)
        expo[i] = e
        scaled[i] = e * r[i]
    return {"scaled_returns": scaled, "exposure": expo}


def vol_managed_backtest(returns, target_vol: float = 0.15, window: int = 20,
                         max_leverage: float = 1.0) -> dict:
    """Compare la série brute à sa version à volatilité gérée (Sharpe, CAGR, drawdown)."""
    r = np.asarray(returns, dtype=float)
    if r.size < 30:
        return {"available": False}
    vm = volatility_managed(r, target_vol=target_vol, window=window, max_leverage=max_leverage)
    raw, managed = _stats(r), _stats(vm["scaled_returns"])
    if not (raw.get("available") and managed.get("available")):
        return {"available": False}
    return {"available": True, "target_vol": target_vol, "window": window,
            "max_leverage": max_leverage,
            "avg_exposure": round(float(np.mean(vm["exposure"])), 4),
            "raw": raw, "managed": managed,
            "sharpe_gain": round(managed["sharpe"] - raw["sharpe"], 2),
            "cagr_gain": round(managed["cagr"] - raw["cagr"], 4),
            "dd_reduction": round(managed["max_drawdown"] - raw["max_drawdown"], 4)}
