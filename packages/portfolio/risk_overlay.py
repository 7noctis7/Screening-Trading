"""Overlay de risque — UNE exposition recommandée à partir de l'état réel du marché.

Le repo calcule déjà plein de briques (vol réalisée, EWMA, drawdown, régime) mais elles
ne pilotent rien : on les CONNECTE en un seul levier actionnable. C'est l'edge PROUVÉ du
projet (réduction de drawdown), pas une prétention d'alpha.

exposition = taper_drawdown(dd) × fraction_vol(target / max(réalisée, prévue))

- `taper_drawdown` : on réduit la voile quand le drawdown courant approche la limite
  (au-delà du simple kill-switch tout-ou-rien) → on n'aggrave pas une perte par inertie.
- `fraction_vol` : cible une vol de portefeuille, en utilisant la vol PRÉVUE (EWMA, qui
  réagit vite aux chocs) si elle dépasse la réalisée → on baisse AVANT le pic.
numpy pur, point-in-time, testable.
"""

from __future__ import annotations

import numpy as np

from packages.portfolio.risk_advanced import ewma_vol
from packages.portfolio.vol_managed import realized_vol


def drawdown_taper(dd: float, soft: float = -0.10, hard: float = -0.20) -> float:
    """Multiplicateur ∈ [0,1] : 1 au-dessus de `soft`, 0 sous `hard`, linéaire entre.

    `dd` ≤ 0 (drawdown courant). Réduit progressivement l'exposition à l'approche de la
    limite — un kill-switch graduel plutôt que binaire.
    """
    if dd >= soft:
        return 1.0
    if dd <= hard:
        return 0.0
    return round((dd - hard) / (soft - hard), 4)


def vol_target_fraction(target_vol: float, realized: float, forecast: float = 0.0,
                        max_frac: float = 1.0, floor_vol: float = 0.02) -> float:
    """Fraction d'exposition = target / max(réalisée, prévue), plafonnée à `max_frac`.

    `floor_vol` borne le dénominateur (évite une exposition explosive si la vol → 0).
    """
    eff = max(realized, forecast, floor_vol)
    return round(min(max_frac, target_vol / eff), 4)


def recommended_exposure(returns, target_vol: float = 0.10, dd_soft: float = -0.10,
                         dd_hard: float = -0.20, max_frac: float = 1.0,
                         window: int = 20, lam: float = 0.94) -> dict:
    """Exposition brute recommandée ∈ [0, max_frac] depuis une série de rendements.

    Combine le taper de drawdown et la cible de vol (forward-aware via EWMA). Renvoie le
    détail pour audit (drawdown, vol réalisée/prévue, chaque multiplicateur).
    """
    r = np.asarray(returns, dtype=float)
    r = r[~np.isnan(r)]
    if r.size < 20:
        return {"available": False, "n": int(r.size)}
    eq = np.cumprod(1 + r)
    dd = float(eq[-1] / np.maximum.accumulate(eq)[-1] - 1)
    rv = realized_vol(r, window)
    realized = (float(rv[-1]) if not np.isnan(rv[-1])
                else float(r.std() * np.sqrt(252)))
    forecast = ewma_vol(r, lam)                         # vol PRÉVUE (réagit vite)
    taper = drawdown_taper(dd, dd_soft, dd_hard)
    vfrac = vol_target_fraction(target_vol, realized, forecast, max_frac)
    return {"available": True, "n": int(r.size), "drawdown": round(dd, 4),
            "realized_vol": round(realized, 4), "forecast_vol": round(forecast, 4),
            "vol_used": round(max(realized, forecast), 4),
            "dd_taper": taper, "vol_fraction": vfrac,
            "exposure": round(taper * vfrac, 4)}
