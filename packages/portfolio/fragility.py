"""Fragilité (Nassim Taleb — Incerto) : mesurer l'exposition aux extrêmes, pas la moyenne.

Principes appliqués :
  • le risque vit dans les QUEUES (kurtosis, pire jour), pas dans la volatilité moyenne ;
  • asymétrie : préférer une **convexité** positive (skew ≥ 0) ; éviter les profils « ramasser des
    pièces devant un rouleau compresseur » (petits gains réguliers, perte catastrophique) ;
  • **barbell** : combiner très sûr + très risqué plutôt que « moyennement risqué » partout ;
  • éviter la RUINE avant tout (déjà couvert par Monte-Carlo / kill-switch).
Diagnostic numpy pur, testable.
"""

from __future__ import annotations

import numpy as np


def fragility(returns) -> dict:
    """Indicateurs de queue : skew, excès de kurtosis, ratio de queue (CVaR/VaR), pire jour."""
    r = np.asarray(returns, dtype=float)
    r = r[np.isfinite(r)]
    if r.size < 20:
        return {"available": False}
    mu, sd = float(r.mean()), float(r.std())
    z = (r - mu) / sd if sd else r * 0
    skew = float(np.mean(z ** 3))
    exkurt = float(np.mean(z ** 4) - 3.0)
    var95 = float(-np.quantile(r, 0.05))
    tail = r[r <= -var95]
    cvar95 = float(-tail.mean()) if tail.size else var95
    tail_ratio = round(cvar95 / var95, 2) if var95 > 0 else 0.0
    worst = float(r.min())
    # "fragile" si queues lourdes (kurtosis élevé) et asymétrie négative (gros risque baissier)
    fragile = exkurt > 3.0 or skew < -0.5 or tail_ratio > 1.6
    return {"available": True, "skew": round(skew, 2), "excess_kurtosis": round(exkurt, 2),
            "tail_ratio": tail_ratio, "worst_day": round(worst, 4), "fragile": bool(fragile),
            "verdict": "fragile (queues lourdes / asymétrie négative)" if fragile
                       else "robuste (queues maîtrisées)"}
