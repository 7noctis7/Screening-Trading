"""Backtest comparatif des PONDÉRATIONS (à sélection fixe) — point-in-time, net de frais.

On garde le MÊME univers et on ne compare QUE la façon de pondérer :
  équipondéré · inverse-vol · variance-min · risk-parity (ERC).
Covariance estimée sur fenêtre glissante (≤ t, sans fuite). Une **bande de non-trading**
réduit le turnover. Métriques : CAGR, Sharpe, Sharpe déflaté, max DD, turnover (annualisé), net de frais.
But : trouver le meilleur couple rendement/risque SANS toucher à la sélection. Numpy pur.
"""

from __future__ import annotations

import numpy as np

from packages.portfolio.optimize import (equal_risk_contribution, inverse_variance_weights,
                                          min_variance_weights)
from packages.portfolio.psr import deflated_sharpe_ratio


def _metrics(rets: list[float], per_year: float, n_trials: int) -> dict:
    r = np.asarray(rets, dtype=float)
    if r.size < 3:
        return {"available": False}
    eq = np.cumprod(1 + r)
    total = float(eq[-1] - 1)
    cagr = float((1 + total) ** (per_year / r.size) - 1) if total > -1 else -1.0
    sd = float(r.std())
    sharpe = float(r.mean() / sd * np.sqrt(per_year)) if sd > 0 else 0.0
    mdd = float((eq / np.maximum.accumulate(eq) - 1).min())
    sr_p = float(r.mean() / sd) if sd > 0 else 0.0
    return {"available": True, "cagr": round(cagr, 4), "sharpe": round(sharpe, 2),
            "max_drawdown": round(mdd, 4), "dsr": deflated_sharpe_ratio(sr_p, r.size, n_trials)}


def _bandify(target: np.ndarray, prev: np.ndarray, band: float) -> np.ndarray:
    """Bande de non-trading : on ne bouge un poids que s'il dérive de plus de `band`."""
    if band <= 0 or prev.sum() == 0:
        return target
    w = np.where(np.abs(target - prev) < band, prev, target)
    s = w.sum()
    return w / s if s > 0 else target


def weighting_backtest(data: dict, step: int = 21, lookback_cov: int = 126, max_assets: int = 120,
                       cost_bps: float = 10.0, band: float = 0.0) -> dict:
    """Compare les schémas de pondération (même univers). Renvoie métriques + turnover par schéma."""
    syms = [s for s, b in data.items() if b and len(b) > lookback_cov + 2 * step][:max_assets]
    if len(syms) < 8:
        return {"available": False}
    L = min(len(data[s]) for s in syms)
    M = np.array([[b.close for b in data[s]][-L:] for s in syms], dtype=float)
    rets = M[:, 1:] / M[:, :-1] - 1
    n = len(syms)
    cost = cost_bps / 1e4
    py = 252.0 / step

    schemes = {
        "Équipondéré": lambda cov, vol: np.full(n, 1.0 / n),
        "Inverse-vol": lambda cov, vol: np.array(inverse_variance_weights(cov)),
        "Variance-min": lambda cov, vol: np.array(min_variance_weights(cov)),
        "Risk-parity (ERC)": lambda cov, vol: np.array(equal_risk_contribution(cov)),
    }
    out = {name: {"rets": [], "prev": np.zeros(n), "turn": 0.0} for name in schemes}
    rebs = 0
    for t in range(lookback_cov, L - 1, step):
        win = rets[:, t - lookback_cov:t]
        cov = np.cov(win) * 252.0
        fwd = M[:, min(t + step, L - 1)] / M[:, t] - 1
        for name, fn in schemes.items():
            try:
                w = fn(cov, None)
            except Exception:  # noqa: BLE001
                w = np.full(n, 1.0 / n)
            w = np.clip(np.nan_to_num(w), 0, None)
            w = w / (w.sum() or 1.0)
            w = _bandify(w, out[name]["prev"], band)
            to = float(np.abs(w - out[name]["prev"]).sum())
            out[name]["rets"].append(float((w * fwd).sum()) - to * cost)
            out[name]["turn"] += to
            out[name]["prev"] = w
        rebs += 1
    if rebs < 3:
        return {"available": False}
    res = {"available": True, "n_rebalances": rebs, "n_assets": n, "step_days": step,
           "lookback_cov": lookback_cov, "band": band, "cost_bps": cost_bps, "schemes": {}}
    for name in schemes:
        m = _metrics(out[name]["rets"], py, n_trials=4)
        m["turnover_annual"] = round(out[name]["turn"] / rebs * py, 2)
        res["schemes"][name] = m
    return res
