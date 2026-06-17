"""Limites de concentration & d'exposition — contrôle de portefeuille (best practice buy-side).

Calcule la concentration (HHI, nombre effectif de positions), les expositions par nom et par
secteur, et liste les **dépassements** de limites. Pur (dict/list), testable hors-ligne.
"""

from __future__ import annotations


def _hhi(weights: list[float]) -> float:
    """Indice de Herfindahl-Hirschman (concentration) ∈ [1/n, 1]."""
    return round(sum(w * w for w in weights), 4)


def concentration_report(weights_by_name: dict[str, float],
                         weights_by_sector: dict[str, float] | None = None,
                         max_name: float = 0.20, max_sector: float = 0.40) -> dict:
    """Rapport de concentration + dépassements.

    Args:
        weights_by_name: poids par actif (fraction du portefeuille, somme ≈ 1).
        weights_by_sector: poids agrégés par secteur (optionnel).
        max_name / max_sector: plafonds réglementaires/internes.
    Returns:
        {hhi, effective_n, top_name, top_name_weight, breaches:[{type,label,weight,limit}]}.
    """
    names = weights_by_name or {}
    ws = list(names.values())
    hhi = _hhi(ws) if ws else 0.0
    eff_n = round(1.0 / hhi, 1) if hhi > 0 else 0.0
    breaches: list[dict] = []
    for nm, w in sorted(names.items(), key=lambda kv: -kv[1]):
        if w > max_name:
            breaches.append({"type": "nom", "label": nm, "weight": round(w, 4), "limit": max_name})
    for sec, w in sorted((weights_by_sector or {}).items(), key=lambda kv: -kv[1]):
        if w > max_sector:
            breaches.append({"type": "secteur", "label": sec, "weight": round(w, 4),
                             "limit": max_sector})
    top_name, top_w = (max(names.items(), key=lambda kv: kv[1]) if names else ("—", 0.0))
    return {"hhi": hhi, "effective_n": eff_n, "n_positions": len(names),
            "top_name": top_name, "top_name_weight": round(top_w, 4),
            "max_name": max_name, "max_sector": max_sector,
            "breaches": breaches, "ok": not breaches}
