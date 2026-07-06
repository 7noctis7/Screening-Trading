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
                         max_name: float = 0.20, max_sector: float = 0.40,
                         index_names: set[str] | frozenset[str] | None = None,
                         max_index: float = 0.60) -> dict:
    """Rapport de concentration + dépassements.

    Args:
        weights_by_name: poids par actif (fraction du portefeuille, somme ≈ 1).
        weights_by_sector: poids agrégés par secteur (optionnel).
        max_name / max_sector: plafonds réglementaires/internes.
        index_names: véhicules INDICIELS larges (ETF trackers, ex. QQQ). Un tracker n'est
            pas un risque d'émetteur unique (look-through, esprit UCITS) → plafond dédié
            `max_index` (0.60 = cible structurelle du cœur 45 % + marge, PAS un plafond
            de stock-picking). Fix audit 06/07 : le cœur QQQ déclenchait à tort la
            limite « nom » 20 % → n_breaches=2 permanent, alarme devenue bruit.
    Returns:
        {hhi, effective_n, top_name, top_name_weight, breaches:[{type,label,weight,limit}]}.
    """
    names = weights_by_name or {}
    ws = list(names.values())
    hhi = _hhi(ws) if ws else 0.0
    eff_n = round(1.0 / hhi, 1) if hhi > 0 else 0.0
    breaches: list[dict] = []
    idx = index_names or set()
    for nm, w in sorted(names.items(), key=lambda kv: -kv[1]):
        cap, kind = (max_index, "indice") if nm in idx else (max_name, "nom")
        if w > cap:
            breaches.append({"type": kind, "label": nm, "weight": round(w, 4), "limit": cap})
    for sec, w in sorted((weights_by_sector or {}).items(), key=lambda kv: -kv[1]):
        if w > max_sector:
            breaches.append({"type": "secteur", "label": sec, "weight": round(w, 4),
                             "limit": max_sector})
    top_name, top_w = (max(names.items(), key=lambda kv: kv[1]) if names else ("—", 0.0))
    return {"hhi": hhi, "effective_n": eff_n, "n_positions": len(names),
            "top_name": top_name, "top_name_weight": round(top_w, 4),
            "max_name": max_name, "max_sector": max_sector,
            "breaches": breaches, "ok": not breaches}


def correlation_aware_caps(base_max_name: float, base_max_sector: float,
                           corr_report: dict | None = None, tighten: float = 0.5,
                           stress_corr: float = 0.75) -> tuple[float, float, bool]:
    """Resserre les plafonds de concentration quand la diversification s'effondre.

    En stress, des actifs « diversifiés » convergent vers corr≈1 → le portefeuille
    devient un pseudo-indice. Si `conditional_correlation` signale un breakdown (ou une
    corr de stress > `stress_corr`), on divise les plafonds par 2 (`tighten`) → plus de
    noms imposés. Renvoie (max_name, max_sector, tightened).
    """
    if not corr_report or not corr_report.get("available"):
        return base_max_name, base_max_sector, False
    cs = corr_report.get("avg_corr_stress")
    tight = bool(corr_report.get("diversification_breakdown")) or (
        cs is not None and cs > stress_corr)
    if tight:
        return (round(base_max_name * tighten, 4),
                round(base_max_sector * tighten, 4), True)
    return base_max_name, base_max_sector, False


def concentration_report_adaptive(weights_by_name: dict[str, float],
                                  weights_by_sector: dict[str, float] | None = None,
                                  corr_report: dict | None = None,
                                  max_name: float = 0.20, max_sector: float = 0.40,
                                  tighten: float = 0.5,
                                  stress_corr: float = 0.75,
                                  index_names: set[str] | frozenset[str] | None = None,
                                  max_index: float = 0.60) -> dict:
    """`concentration_report` avec plafonds RESSERRÉS si breakdown de corrélation.

    Ferme le gap d'audit : `conditional_correlation` ne faisait que signaler ; ici il
    PILOTE les limites. Renvoie le rapport + `tightened` / corr de stress.
    """
    mn, ms, tightened = correlation_aware_caps(max_name, max_sector, corr_report,
                                               tighten, stress_corr)
    rep = concentration_report(weights_by_name, weights_by_sector, mn, ms,
                               index_names=index_names, max_index=max_index)
    rep["tightened"] = tightened
    rep["base_max_name"] = max_name
    rep["base_max_sector"] = max_sector
    if corr_report and corr_report.get("available"):
        rep["avg_corr_stress"] = corr_report.get("avg_corr_stress")
        rep["diversification_breakdown"] = bool(
            corr_report.get("diversification_breakdown"))
    return rep
