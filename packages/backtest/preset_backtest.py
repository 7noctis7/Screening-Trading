"""Backtest du PRESET stratégique « best practice » (point-in-time, anti-fuite).

Combine, à chaque rebalancement :
  1. **Tilt qualité** : univers = top-K par score fondamental (statique → neutre vis-à-vis des prix,
     pas de fuite ; c'est un *sleeve* facteur qualité).
  2. **Risk-parity (ERC)** : chaque actif contribue également au risque (covariance trailing).
  3. **DD-target exposure** : exposition brute dimensionnée pour viser un drawdown cible
     (vol-cible ≈ DD/2.5), le reste en cash → pilotage par la volatilité réalisée.
  4. **Earnings blackout (proxy)** : on évite d'entrer juste après un choc binaire (|move 2 j| élevé).
  5. **No-trade band** : on ne bouge un poids que s'il dérive de plus de `band` (turnover ↓).
  6. **Coûts par classe d'actifs** déduits du turnover (réalisme).

Compare le preset à l'équipondéré (bench) et, si fourni, à la courbe du swing. numpy pur, testable.
"""

from __future__ import annotations

import numpy as np

from packages.backtest.conviction_backtest import _stats
from packages.execution.costs import CostModel
from packages.portfolio.optimize import equal_risk_contribution


def _cov_annual(win: np.ndarray) -> np.ndarray:
    if win.shape[0] == 1:
        return np.array([[float(win.var()) * 252]])
    return np.cov(win) * 252


def preset_backtest(data: dict, quality: dict | None = None, asset_classes: dict | None = None,
                    swing_equity: list | None = None, dd_target: float = 0.25, band: float = 0.03,
                    step: int = 21, lookback: int = 120, top_k: int = 30, k_dd: float = 2.5,
                    blackout_move: float = 0.12) -> dict:
    syms = [s for s, b in data.items() if b and len(b) > lookback + 2 * step]
    if len(syms) < 5:
        return {"available": False}
    L = min(len(data[s]) for s in syms)
    M = {s: np.asarray([b.close for b in data[s]][-L:], float) for s in syms}
    acmap = asset_classes or {}
    quality = quality or {}

    # univers tilt-qualité (statique → factor sleeve, sans fuite des prix)
    q = {s: quality.get(s) for s in syms if quality.get(s) is not None}
    universe = (sorted(q, key=lambda s: q[s], reverse=True)[:top_k]
                if len(q) >= 5 else syms[:top_k])
    A = np.asarray([M[s] for s in universe])                    # n × L
    rets = A[:, 1:] / A[:, :-1] - 1
    tgt_vol = max(0.0, abs(dd_target)) / k_dd
    rt = np.asarray([CostModel.for_asset_class(acmap.get(s, "equity")).round_trip_bps / 1e4
                     for s in universe])

    prev_w = np.zeros(len(universe))
    port: list[float] = []
    gross_hist: list[float] = []
    turn = 0.0
    start = max(lookback, 50)
    for t in range(start, L - 1, step):
        win = rets[:, max(0, t - lookback):t]
        if win.shape[1] < 20:
            continue
        cov = _cov_annual(win)
        w = np.asarray(equal_risk_contribution(cov), float)     # risk-parity
        last2 = A[:, t] / A[:, t - 2] - 1                       # blackout : évite le post-choc binaire
        w = np.where(np.abs(last2) > blackout_move, 0.0, w)
        ssum = w.sum()
        w = w / ssum if ssum > 0 else w
        pv = float(np.sqrt(max(0.0, w @ cov @ w)))              # DD-target : exposition pilotée par la vol
        gross = 0.0 if pv <= 0 else min(1.0, tgt_vol / pv)
        w = w * gross
        if band > 0 and prev_w.sum() > 0:                       # bande de non-trading
            w = np.where(np.abs(w - prev_w) < band, prev_w, w)
        nxt = min(t + step, L - 1)
        fwd = A[:, nxt] / A[:, t] - 1                           # rendement RÉALISÉ après t
        cost = float((np.abs(w - prev_w) * rt).sum())
        port.append(float((w * fwd).sum()) - cost)
        turn += float(np.abs(w - prev_w).sum())
        gross_hist.append(float(w.sum()))
        prev_w = w
    if len(port) < 3:
        return {"available": False}

    per_year = 252.0 / step

    def _cum(series: list) -> list:
        e = np.cumprod(1 + np.asarray(series, dtype=float))
        return [1.0] + [round(float(x), 4) for x in e]

    out = {"available": True, "step_days": step, "top_k": len(universe),
           "preset": _stats(port, per_year),
           "turnover_annual": round(turn / len(port) * per_year, 2),
           "dd_target": dd_target, "band": band, "target_vol": round(tgt_vol, 4),
           "avg_gross": round(float(np.mean(gross_hist)) if gross_hist else 0.0, 4),
           "curves": {"preset": _cum(port)}}

    # bench équipondéré sur le MÊME univers (apples-to-apples : isole l'apport de la construction
    # risk-parity + DD-target + blackout + band vs un simple équipondéré plein-investi)
    bench = [float((A[:, min(t + step, L - 1)] / A[:, t] - 1).mean())
             for t in range(start, L - 1, step)]
    out["benchmark"] = _stats(bench, per_year)
    out["curves"]["benchmark"] = _cum(bench)

    # swing (depuis sa courbe d'equity), ré-échantillonné sur la même grille
    if swing_equity and len(swing_equity) >= L:
        eq = np.asarray(swing_equity[-L:], float)
        grid = list(range(start, L, step))
        sr = [eq[b] / eq[a] - 1 for a, b in zip(grid[:-1], grid[1:]) if eq[a] > 0]
        if len(sr) >= 3:
            out["swing"] = _stats(sr, per_year)
            out["curves"]["swing"] = _cum(sr)
    return out
