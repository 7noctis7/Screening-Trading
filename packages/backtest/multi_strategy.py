"""Backtest multi-stratégie — compare plusieurs règles et leur ensemble (best practice).

Plusieurs sources d'alpha (tendance, momentum, retour à la moyenne) testées sur la même série,
puis **combinées** (vote moyen). Chaque stratégie est long-only {0,1}. Renvoie pour chacune et
pour l'ensemble : rendement total, Sharpe annualisé, max drawdown, exposition. Numpy pur.
"""

from __future__ import annotations

import numpy as np


def _sma(c: np.ndarray, p: int) -> np.ndarray:
    out = np.full_like(c, np.nan, dtype=float)
    if len(c) >= p:
        cs = np.cumsum(c)
        out[p - 1:] = (cs[p - 1:] - np.concatenate([[0], cs[:-p]])) / p
    return out


def _rsi(c: np.ndarray, p: int = 14) -> np.ndarray:
    d = np.diff(c, prepend=c[0])
    up = np.where(d > 0, d, 0.0)
    dn = np.where(d < 0, -d, 0.0)
    ru = np.convolve(up, np.ones(p) / p, mode="same")
    rd = np.convolve(dn, np.ones(p) / p, mode="same")
    rs = np.divide(ru, rd, out=np.ones_like(ru), where=rd > 0)
    return 100 - 100 / (1 + rs)


def _positions(closes: np.ndarray) -> dict[str, np.ndarray]:
    """Signaux de position {0,1} par stratégie (décalés d'1 barre → anti look-ahead)."""
    sma50 = _sma(closes, 50)
    mom = np.concatenate([np.zeros(63), closes[63:] / closes[:-63] - 1]) if len(closes) > 63 else np.zeros(len(closes))
    rsi = _rsi(closes, 14)
    sig = {
        "Tendance (>MM50)": (closes > sma50).astype(float),
        "Momentum (63j>0)": (mom > 0).astype(float),
        "Retour moyenne (RSI<35)": (rsi < 35).astype(float),
    }
    return {k: np.nan_to_num(np.concatenate([[0.0], v[:-1]])) for k, v in sig.items()}  # shift +1


def _metrics(closes: np.ndarray, pos: np.ndarray) -> dict:
    ret = np.concatenate([[0.0], closes[1:] / closes[:-1] - 1])
    strat = pos * ret
    eq = np.cumprod(1 + strat)
    total = float(eq[-1] - 1)
    sd = strat.std()
    sharpe = float(strat.mean() / sd * np.sqrt(252)) if sd > 0 else 0.0
    peak = np.maximum.accumulate(eq)
    mdd = float((eq / peak - 1).min())
    return {"total_return": round(total, 4), "sharpe": round(sharpe, 2),
            "max_drawdown": round(mdd, 4), "exposure": round(float(pos.mean()), 3)}


def run_multi_strategy(closes, threshold: float = 0.5) -> dict:
    """Backtest des stratégies individuelles + de leur ensemble (vote moyen)."""
    c = np.asarray(closes, dtype=float)
    if c.size < 80:
        return {"available": False}
    pos = _positions(c)
    strategies = [{"name": k, **_metrics(c, v)} for k, v in pos.items()]
    combined_sig = (np.mean(list(pos.values()), axis=0) >= threshold).astype(float)
    combined = {"name": "Ensemble (vote)", **_metrics(c, combined_sig)}
    best = max(strategies, key=lambda s: s["sharpe"])
    return {"available": True, "strategies": strategies, "combined": combined,
            "best": best["name"], "n_bars": int(c.size)}
