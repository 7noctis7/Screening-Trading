"""Alpha decay + impact de marché (Almgren) — robustesse backtest, sous le gate.

- ic_half_life : vitesse d'érosion du pouvoir prédictif (IC) avec l'horizon → demi-vie.
  Sert à savoir QUAND recalibrer un signal face à l'adaptation des concurrents.
- almgren_impact : coût d'impact racine-carrée `η·σ·√(Q/ADV)` pour le backtest
  (évite de surestimer l'alpha net). numpy uniquement.
"""

from __future__ import annotations

import math

import numpy as np


def rolling_ic(signal, fwd_ret, window: int = 60) -> list[float]:
    """IC roulant (Spearman ≈ Pearson sur rangs) entre signal et rendement futur."""
    s = np.asarray(signal, float)
    r = np.asarray(fwd_ret, float)
    out: list[float] = []
    for t in range(window, len(s) + 1):
        a, b = s[t - window:t], r[t - window:t]
        ra = np.argsort(np.argsort(a)).astype(float)
        rb = np.argsort(np.argsort(b)).astype(float)
        if ra.std() > 0 and rb.std() > 0:
            out.append(float(np.corrcoef(ra, rb)[0, 1]))
    return out


def ic_half_life(ics_by_horizon: list[float]) -> dict:
    """Demi-vie de l'alpha : ajuste |IC_h| ≈ IC₀·e^(−λh) → demi-vie = ln2/λ.

    `ics_by_horizon` = IC du signal aux horizons h=1,2,…,H. Décroissance rapide
    (demi-vie courte) = signal périssable → recalibrer souvent.
    """
    y = [abs(x) for x in ics_by_horizon if x is not None and abs(x) > 1e-9]
    if len(y) < 3:
        return {"available": False}
    h = np.arange(len(y), dtype=float)
    slope, _ = np.polyfit(h, np.log(y), 1)
    lam = -float(slope)
    if lam <= 1e-9:
        return {"available": True, "half_life": float("inf"), "lambda": round(lam, 5),
                "decays": False}
    return {"available": True, "half_life": round(math.log(2) / lam, 2),
            "lambda": round(lam, 5), "decays": True}


def almgren_impact(qty: float, adv: float, sigma: float, eta: float = 1.0) -> float:
    """Impact temporaire racine-carrée (Almgren) en FRACTION du prix.

    qty = taille de l'ordre, adv = volume quotidien moyen, sigma = vol quotidienne.
    Coût ≈ η·σ·√(qty/ADV). Non-linéaire : payer 4× la taille coûte 2× l'impact.
    """
    if adv <= 0 or qty <= 0:
        return 0.0
    return eta * sigma * math.sqrt(qty / adv)


def apply_impact(gross_returns, turnover_per_period: float, adv_ratio: float,
                 sigma: float, eta: float = 1.0) -> np.ndarray:
    """Déduit l'impact Almgren des rendements bruts à chaque rotation.

    turnover_per_period = fraction du portefeuille tradée/barre ; adv_ratio = taille
    typique d'ordre / ADV. Drag = turnover × η·σ·√(adv_ratio) par barre.
    """
    drag = turnover_per_period * almgren_impact(adv_ratio, 1.0, sigma, eta)
    return np.asarray(gross_returns, float) - drag
