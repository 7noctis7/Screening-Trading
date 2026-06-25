"""Sensibilité — un screening/régime est-il STABLE quand on bouge les seuils ?

Un seuil main-tuné qui change radicalement la sélection au moindre ajustement est
fragile (sur-optimisé). On mesure :
- screening : stabilité Jaccard de la sélection top-N quand on perturbe chaque seuil ;
- régime : dérive moyenne de l'exposition quand on perturbe les seuils du gate.
Pur (stdlib/numpy), testable hors-ligne.
"""

from __future__ import annotations


def jaccard(a, b) -> float:
    """|A∩B| / |A∪B| ∈ [0,1]. 1 = identique, 0 = disjoint. Vide∩vide = 1."""
    sa, sb = set(a), set(b)
    union = sa | sb
    return len(sa & sb) / len(union) if union else 1.0


def selection_stability(baseline, variants, stable_at: float = 0.7) -> dict:
    """Stabilité d'une sélection : Jaccard de chaque variante vs baseline.

    `baseline` = liste de symboles de référence ; `variants` = liste de sélections
    obtenues en perturbant un seuil. `stable` si le PIRE Jaccard ≥ `stable_at`.
    """
    js = [round(jaccard(baseline, v), 3) for v in variants]
    if not js:
        return {"available": False}
    mn = min(js)
    return {"available": True, "jaccard_min": mn,
            "jaccard_mean": round(sum(js) / len(js), 3),
            "jaccards": js, "stable": bool(mn >= stable_at)}


def regime_exposure_shift(mkt, base_kwargs: dict, perturbed_kwargs: dict,
                          start: int = 25) -> dict:
    """Dérive moyenne de l'exposition du gate de régime entre deux jeux de seuils.

    Mesure |mult_base − mult_perturbé| moyen sur la série marché → un gate robuste
    bouge peu quand on perturbe ses seuils main-tunés.
    """
    import numpy as np

    from packages.backtest.preset_backtest import _regime_mult
    m = np.asarray(mkt, float)
    if m.size <= start:
        return {"available": False}
    diffs = [abs(_regime_mult(m, t, **base_kwargs)
                 - _regime_mult(m, t, **perturbed_kwargs))
             for t in range(start, m.size)]
    mean_shift = float(sum(diffs) / len(diffs)) if diffs else 0.0
    return {"available": True, "mean_exposure_shift": round(mean_shift, 4),
            "max_exposure_shift": round(max(diffs), 4) if diffs else 0.0,
            "stable": bool(mean_shift < 0.1)}
