"""Test de SABOTAGE adverse — l'edge survit-il à une exécution dégradée ?

Philosophie « zéro confiance » : un backtest gagnant est présumé chanceux jusqu'à
preuve du contraire. On dégrade la série (coût ×3 ≈ spreads +300 %, bruit, latence) et
on regarde si l'edge tient. Verdict BINAIRE (survit / s'effondre). Complète DSR/PBO
(sur-apprentissage) par la robustesse d'EXÉCUTION. numpy pur, déterministe, hors-ligne.
"""

from __future__ import annotations

import numpy as np

from packages.portfolio.metrics import perf_summary


def roll_spread(prices) -> float:
    """Spread effectif implicite (estimateur de Roll) : 2·√(−Cov(Δpₜ, Δpₜ₋₁)).

    Ancre le coût du sabotage sur la microstructure RÉELLE de l'actif (au lieu d'un
    bruit arbitraire). 0 si l'autocovariance est positive (pas de signature de spread).
    """
    p = np.asarray(prices, float)
    if p.size < 3:
        return 0.0
    dp = np.diff(p)
    cov = float(np.cov(dp[:-1], dp[1:])[0, 1])
    return 2.0 * np.sqrt(-cov) if cov < 0 else 0.0


def sabotage_sweep(returns, *, levels=(1.0, 2.0, 3.0, 5.0), base_cost_bps: float = 10.0,
                   seed: int = 0) -> dict:
    """Balayage de robustesse : rétention de Sharpe vs niveau de stress croissant.

    Au lieu d'un pass/fail binaire à un calibrage arbitraire, on trace la dégradation
    et on reporte le **niveau de rupture** (rétention < 0,5). Un edge robuste a une
    marge ; un fragile casse tôt → élimine le risque de mauvais calibrage unique.
    """
    clean = perf_summary(returns)
    if not clean.get("available") or clean["sharpe"] <= 0:
        return {"available": False}
    cs = clean["sharpe"]
    curve, breakeven = [], None
    for m in levels:
        deg = stress_returns(returns, extra_cost_bps=base_cost_bps * m,
                             noise_mult=0.25 * m, latency=1, seed=seed)
        ss = perf_summary(deg)["sharpe"]
        ret = round(ss / cs, 3) if cs > 0 else 0.0
        curve.append({"stress": m, "sharpe": ss, "retention": ret})
        if breakeven is None and ret < 0.5:
            breakeven = m
    robust = breakeven is None or breakeven >= 3.0
    return {"available": True, "clean_sharpe": cs, "curve": curve,
            "breakeven_stress": breakeven, "robust": robust}


def stress_returns(returns, *, extra_cost_bps: float = 30.0, noise_mult: float = 0.5,
                   latency: int = 1, seed: int = 0, turnover=None) -> np.ndarray:
    """Dégrade une série de rendements (pire cas d'exécution).

    - `latency` : tu agis en RETARD → décalage des rendements (tu rates le début).
    - `noise_mult` : bruit de prix ~ N(0, noise_mult·σ).
    - `extra_cost_bps` : spread/slippage aggravés.
    - `turnover` (audit 07/17, M-2) : coût facturé sur le **Δposition** de la barre
      (|Δpoids| ∈ [0,2]), PAS à chaque barre. Un scalaire = turnover moyen appliqué
      uniformément ; un tableau aligné = coût par barre. None → coût à CHAQUE barre
      (worst-case historique : surfacture une stratégie faible turnover comme un B&H).
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
    haircut = extra_cost_bps / 1e4
    if turnover is None:
        return out - haircut
    to = np.asarray(turnover, float)
    if to.ndim == 0:                                    # scalaire → turnover moyen/barre
        return out - haircut * float(to)
    to = to[:out.size] if to.size >= out.size else np.pad(to, (0, out.size - to.size))
    return out - haircut * to                           # coût ∝ |Δposition| de la barre


def sabotage_verdict(returns, *, retention_min: float = 0.5,
                     extra_cost_bps: float = 30.0, noise_mult: float = 0.5,
                     latency: int = 1, seed: int = 0, turnover=None) -> dict:
    """Binaire : l'edge SURVIT-il au sabotage ? (Sharpe > 0 ET ≥ `retention_min`).

    `turnover` (M-2) : facture le coût sur le Δposition (cf. `stress_returns`) — sans lui,
    le coût est prélevé à chaque barre (worst-case, pénalise à tort le faible turnover).
    Renvoie {available, survives, clean_sharpe, stressed_sharpe, sharpe_retention,
    stressed_maxdd}. Rétention = Sharpe stressé / Sharpe propre.
    """
    clean = perf_summary(returns)
    if not clean.get("available"):
        return {"available": False}
    deg = stress_returns(returns, extra_cost_bps=extra_cost_bps, noise_mult=noise_mult,
                         latency=latency, seed=seed, turnover=turnover)
    s = perf_summary(deg)
    cs, ss = clean["sharpe"], s["sharpe"]
    retention = round(ss / cs, 3) if cs > 0 else (1.0 if ss >= cs else 0.0)
    survives = bool(ss > 0 and (cs <= 0 or retention >= retention_min))
    return {"available": True, "survives": survives, "clean_sharpe": cs,
            "stressed_sharpe": ss, "sharpe_retention": retention,
            "stressed_maxdd": s["max_drawdown"]}
