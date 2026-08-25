"""Alpha, bêta, et excès — ce qu'un backtest long-only doit prouver avant d'être un candidat.

Sortie du 25/08 : les cinq hypothèses testées donnent un Sharpe long-only entre 0,95 et 1,70,
et un Sharpe long/short entre −1,28 et +0,76. Le même signal, la même période, la même exécution.
L'écart entre les deux colonnes n'est pas une propriété du signal, c'est du BÊTA : un panier
long-only de titres américains sur une période haussière monte parce que le marché monte.

Un « ✅ CANDIDAT » long-only qui n'est pas comparé à la détention de l'univers ne dit donc rien.
Ce n'est pas un seuil discutable, c'est une définition : une stratégie long-only qui fait moins
bien que l'équipondéré du même univers n'a pas d'intérêt, quel que soit son Sharpe absolu.

`alpha` est annualisé et net de coûts ; `beta` est la sensibilité au benchmark ; `ir_exces` est
le ratio d'information de la série d'excès (strat − benchmark), la mesure qui décide.
"""

from __future__ import annotations

import numpy as np


def attribution(strat: np.ndarray, bench: np.ndarray, per_year: float) -> dict:
    """Décompose une série de rendements période par période face à son benchmark.

    Les deux séries doivent partager la même grille : on tronque sur la plus courte plutôt que
    d'aligner à l'aveugle — un décalage d'une période inventerait de l'alpha."""
    s = np.asarray(strat, dtype=float)
    b = np.asarray(bench, dtype=float)
    m = min(s.size, b.size)
    if m < 8:
        return {"available": False, "n": int(m)}
    s, b = s[-m:], b[-m:]
    var_b = float(b.var(ddof=1))
    beta = float(np.cov(s, b, ddof=1)[0, 1] / var_b) if var_b > 0 else 0.0
    alpha_periode = float(s.mean() - beta * b.mean())
    exces = s - b
    sd_e = float(exces.std(ddof=1))
    sd_s, sd_b = float(s.std(ddof=1)), float(b.std(ddof=1))
    return {"available": True, "n": int(m),
            "beta": round(beta, 3),
            "alpha_annuel": round(float((1.0 + alpha_periode) ** per_year - 1.0), 4),
            "ir_exces": round(float(exces.mean() / sd_e * np.sqrt(per_year)), 3) if sd_e > 0 else 0.0,
            "exces_annuel": round(float((1.0 + exces.mean()) ** per_year - 1.0), 4),
            "sharpe_strat": round(float(s.mean() / sd_s * np.sqrt(per_year)), 3) if sd_s > 0 else 0.0,
            "sharpe_bench": round(float(b.mean() / sd_b * np.sqrt(per_year)), 3) if sd_b > 0 else 0.0}


def bat_le_benchmark(att: dict) -> bool:
    """Le candidat apporte-t-il quelque chose que la détention de l'univers n'apporte pas ?

    Les deux conditions sont volontairement minimales — un alpha positif ET un excès positif.
    Ce n'est pas un gate de performance, c'est un gate de PERTINENCE : en dessous, la stratégie
    est une façon coûteuse d'acheter le marché."""
    return bool(att.get("available")) and att["alpha_annuel"] > 0 and att["ir_exces"] > 0
