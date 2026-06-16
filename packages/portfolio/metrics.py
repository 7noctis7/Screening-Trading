"""Métriques de performance & risque — à partir d'une courbe d'equity / de trades.

Pures (numpy). Mêmes formules en backtest et en live. Pas de chiffre inventé.
"""

from __future__ import annotations

import numpy as np

_PPY = 252  # périodes par an (daily)


def returns_from_equity(equity: list[float]) -> np.ndarray:
    e = np.asarray(equity, float)
    if e.size < 2:
        return np.array([])
    return e[1:] / e[:-1] - 1.0


def sharpe(equity, rf: float = 0.0, ppy: int = _PPY) -> float:
    r = returns_from_equity(equity)
    if r.size < 2 or r.std(ddof=1) == 0:
        return 0.0
    excess = r - rf / ppy
    return float(excess.mean() / r.std(ddof=1) * np.sqrt(ppy))


def sortino(equity, rf: float = 0.0, ppy: int = _PPY) -> float:
    r = returns_from_equity(equity)
    downside = r[r < 0]
    if downside.size == 0 or downside.std(ddof=1) == 0:
        return 0.0
    excess = r.mean() - rf / ppy
    return float(excess / downside.std(ddof=1) * np.sqrt(ppy))


def max_drawdown(equity) -> float:
    e = np.asarray(equity, float)
    if e.size == 0:
        return 0.0
    peak = np.maximum.accumulate(e)
    return float((e / peak - 1.0).min())


def calmar(equity, ppy: int = _PPY) -> float:
    e = np.asarray(equity, float)
    if e.size < 2:
        return 0.0
    total = e[-1] / e[0] - 1.0
    years = e.size / ppy
    cagr = (1 + total) ** (1 / years) - 1 if years > 0 and (1 + total) > 0 else 0.0
    mdd = abs(max_drawdown(e))
    return float(cagr / mdd) if mdd > 0 else 0.0


def trade_stats(pnls: list[float]) -> dict[str, float]:
    a = np.asarray(pnls, float)
    if a.size == 0:
        return {"n": 0, "win_rate": 0.0, "profit_factor": 0.0, "expectancy": 0.0}
    wins, losses = a[a > 0], a[a < 0]
    gross_win, gross_loss = wins.sum(), -losses.sum()
    return {
        "n": int(a.size),
        "win_rate": float(wins.size / a.size),
        "profit_factor": float(gross_win / gross_loss) if gross_loss > 0 else float("inf"),
        "expectancy": float(a.mean()),
        "avg_win": float(wins.mean()) if wins.size else 0.0,
        "avg_loss": float(losses.mean()) if losses.size else 0.0,
    }


def summary(equity: list[float], pnls: list[float]) -> dict[str, float]:
    e = np.asarray(equity, float)
    total_return = float(e[-1] / e[0] - 1.0) if e.size >= 2 else 0.0
    return {
        "total_return": total_return,
        "sharpe": sharpe(equity),
        "sortino": sortino(equity),
        "calmar": calmar(equity),
        "max_drawdown": max_drawdown(equity),
        **trade_stats(pnls),
    }
