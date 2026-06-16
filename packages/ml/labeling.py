"""Labeling triple-barrière + meta-labeling (López de Prado, AFML ch. 3).

Triple-barrière : pour chaque entrée, on pose 3 barrières — profit (haut), stop (bas),
et temps (horizon). Le label = la 1re barrière touchée (+1 profit, -1 stop, signe du
rendement si seul le temps est atteint). Bien plus réaliste qu'un rendement à horizon fixe.

Meta-labeling : un modèle primaire donne le SENS ; le méta-modèle apprend s'il faut AGIR
(label binaire = le trade primaire aurait-il été gagnant). Sépare "direction" et "taille".
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(slots=True)
class Label:
    entry_idx: int
    exit_idx: int
    ret: float
    label: int  # +1 profit / -1 stop / 0 neutre (barrière temps)
    touched: str  # "pt" | "sl" | "time"


def ewm_volatility(close: np.ndarray, span: int = 20) -> np.ndarray:
    """Volatilité EWM des rendements (pour des barrières dynamiques)."""
    rets = np.zeros_like(close, dtype=float)
    rets[1:] = close[1:] / close[:-1] - 1.0
    alpha = 2.0 / (span + 1.0)
    var = np.zeros_like(rets)
    mean = 0.0
    v = 0.0
    for i, r in enumerate(rets):
        mean = alpha * r + (1 - alpha) * mean
        v = alpha * (r - mean) ** 2 + (1 - alpha) * v
        var[i] = v
    return np.sqrt(var)


def triple_barrier(close: np.ndarray, entries: list[int], pt: float = 2.0,
                   sl: float = 2.0, vol: np.ndarray | float | None = None,
                   horizon: int = 20) -> list[Label]:
    """Étiquette chaque entrée selon la 1re barrière touchée."""
    n = len(close)
    if vol is None:
        vol = ewm_volatility(close)
    if np.isscalar(vol):
        vol = np.full(n, float(vol))
    out: list[Label] = []
    for i in entries:
        if i >= n - 1:
            continue
        up, dn = pt * vol[i], -sl * vol[i]
        end = min(i + horizon, n - 1)
        touched, exit_idx, lbl = "time", end, 0
        for j in range(i + 1, end + 1):
            r = close[j] / close[i] - 1.0
            if r >= up:
                touched, exit_idx, lbl = "pt", j, 1
                break
            if r <= dn:
                touched, exit_idx, lbl = "sl", j, -1
                break
        ret = close[exit_idx] / close[i] - 1.0
        if touched == "time":
            lbl = int(np.sign(ret))
        out.append(Label(i, exit_idx, float(ret), lbl, touched))
    return out


def meta_labels(labels: list[Label], side: int = 1) -> np.ndarray:
    """Méta-label binaire : 1 si le trade (dans le sens `side`) aurait été gagnant."""
    return np.array([1 if (lab.ret * side) > 0 else 0 for lab in labels], dtype=int)
