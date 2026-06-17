"""Note de conviction — fusion multi-signaux (best practice modèle multi-facteurs).

Combine plusieurs lentilles d'alpha en UNE note comparable : tendance/momentum, proba ML,
qualité fondamentale, sentiment. Méthode disciplinée (anti-surapprentissage) :
  1. z-score de chaque composante en cross-section (comparable entre actifs),
  2. moyenne à **poids égaux** des composantes disponibles (pas de poids « optimisés »),
  3. classement → sélection du haut + sizing par conviction (sous contrôle du risque côté appelant).
Numpy/stdlib, pur, testable.
"""

from __future__ import annotations

import numpy as np

COMPONENTS = ("trend", "ml", "fundamental", "sentiment")


def _zmap(signals: dict, comp: str) -> dict:
    """z-scores d'une composante sur les actifs qui la possèdent."""
    pairs = [(s, sig[comp]) for s, sig in signals.items() if sig.get(comp) is not None]
    if len(pairs) < 2:
        return {s: 0.0 for s, _ in pairs}
    vals = np.array([v for _, v in pairs], dtype=float)
    mu, sd = float(vals.mean()), float(vals.std()) or 1.0
    return {s: (v - mu) / sd for s, v in pairs}


def conviction_rank(signals: dict[str, dict], weights: dict[str, float] | None = None) -> list[dict]:
    """Classe les actifs par note de conviction (moyenne des z-scores des composantes présentes)."""
    z = {c: _zmap(signals, c) for c in COMPONENTS}
    w = weights or {c: 1.0 for c in COMPONENTS}
    out = []
    for s in signals:
        parts = {c: round(z[c][s], 3) for c in COMPONENTS if s in z[c]}
        if parts:
            score = sum(w.get(c, 1.0) * v for c, v in parts.items()) / sum(w.get(c, 1.0) for c in parts)
        else:
            score = 0.0
        out.append({"symbol": s, "conviction": round(float(score), 3), "components": parts})
    out.sort(key=lambda r: r["conviction"], reverse=True)
    return out


def conviction_weights(ranked: list[dict], vol: dict[str, float] | None = None,
                       top_n: int = 15, max_weight: float = 0.20) -> dict[str, float]:
    """Allocation pilotée par conviction × inverse-vol (longs only), plafonnée et normalisée.

    Best practice : ne garder que les convictions positives, pondérer à l'inverse de la volatilité
    (contrôle du risque), plafonner par position, renormaliser.
    """
    pos = [r for r in ranked if r["conviction"] > 0][:top_n]
    if not pos:
        return {}
    raw = {}
    for r in pos:
        v = (vol or {}).get(r["symbol"], 0.0)
        inv = 1.0 / v if v and v > 0 else 1.0
        raw[r["symbol"]] = r["conviction"] * inv
    tot = sum(raw.values()) or 1.0
    w = {s: x / tot for s, x in raw.items()}
    # plafonnement itératif + renormalisation
    for _ in range(8):
        over = {s: x for s, x in w.items() if x > max_weight}
        if not over:
            break
        for s in over:
            w[s] = max_weight
        rest = [s for s in w if w[s] < max_weight]
        deficit = 1.0 - sum(w.values())
        base = sum(w[s] for s in rest) or 1.0
        for s in rest:
            w[s] += deficit * w[s] / base
    return {s: round(x, 4) for s, x in w.items()}
