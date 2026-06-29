"""Test de SABOTAGE adverse — l'edge survit-il à une exécution dégradée ?

Philosophie « zéro confiance » : un backtest gagnant est présumé chanceux jusqu'à
preuve du contraire. On dégrade la série (coût ×3 ≈ spreads +300 %, bruit, latence) et
on regarde si l'edge tient. Verdict BINAIRE (survit / s'effondre). Complète DSR/PBO
(sur-apprentissage) par la robustesse d'EXÉCUTION. numpy pur, déterministe, hors-ligne.
"""

from __future__ import annotations

import numpy as np

from packages.portfolio.metrics import perf_summary


def stress_returns(returns, *, extra_cost_bps: float = 30.0, noise_mult: float = 0.5,
                   latency: int = 1, seed: int = 0) -> np.ndarray:
    """Dégrade une série de rendements (pire cas d'exécution).

    - `latency` : tu agis en RETARD → décalage des rendements (tu rates le début).
    - `noise_mult` : bruit de prix ~ N(0, noise_mult·σ).
    - `extra_cost_bps` : spread/slippage aggravés → haircut/période (~3× RT actions).
    """
    r = np.asarray([x for x in returns if x == x], float)
    if r.size == 0:
        return r
    out = r.copy()
    if latency > 0:
        out = np.roll(out, latency)
        out[:latency] = 0.0
    if noise_mult > 0:
        rng = np.random.default_rng(seed)
        out = out + rng.normal(0.0, noise_mult * float(r.std()), r.size)
    return out - extra_cost_bps / 1e4


def sabotage_verdict(returns, *, retention_min: float = 0.5,
                     extra_cost_bps: float = 30.0, noise_mult: float = 0.5,
                     latency: int = 1, seed: int = 0) -> dict:
    """Binaire : l'edge SURVIT-il au sabotage ? (Sharpe > 0 ET ≥ `retention_min`).

    Renvoie {available, survives, clean_sharpe, stressed_sharpe, sharpe_retention,
    stressed_maxdd}. Rétention = Sharpe stressé / Sharpe propre.
    """
    clean = perf_summary(returns)
    if not clean.get("available"):
        return {"available": False}
    deg = stress_returns(returns, extra_cost_bps=extra_cost_bps, noise_mult=noise_mult,
                         latency=latency, seed=seed)
    s = perf_summary(deg)
    cs, ss = clean["sharpe"], s["sharpe"]
    retention = round(ss / cs, 3) if cs > 0 else (1.0 if ss >= cs else 0.0)
    survives = bool(ss > 0 and (cs <= 0 or retention >= retention_min))
    return {"available": True, "survives": survives, "clean_sharpe": cs,
            "stressed_sharpe": ss, "sharpe_retention": retention,
            "stressed_maxdd": s["max_drawdown"]}
