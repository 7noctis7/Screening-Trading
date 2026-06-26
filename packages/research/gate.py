"""Gate de promotion — LE Checker unique : un candidat est-il promouvable ?

Avant, la décision « promu/rejeté » était dupliquée en inline dans chaque script (seuils
parfois différents). On la centralise ici → une seule définition, testée, partagée par
tous les backtests/event-studies. C'est le pilier Maker-Checker rendu structurel :
le Maker génère, CE module tranche, selon des critères déterministes (pas un 2e LLM).

Critères (un contrôle à None est IGNORÉ — pas encore mesuré, ne bloque pas) :
- placebo p-value < `placebo_max` (l'effet bat le hasard)
- DSR > `dsr_min`            (Sharpe déflaté du multiple-testing, López de Prado)
- PBO < `pbo_max`            (pas de surajustement du choix de config, CSCV)
- edge net > 0               (rentable APRÈS coûts)
"""

from __future__ import annotations

# Seuils par défaut = SOURCE UNIQUE DE VÉRITÉ (étaient en dur, dispersés).
DSR_MIN = 0.5
PBO_MAX = 0.5
PLACEBO_MAX = 0.05


def promotion_verdict(*, dsr: float | None = None, pbo: float | None = None,
                      edge: float | None = None, placebo_p: float | None = None,
                      dsr_min: float = DSR_MIN, pbo_max: float = PBO_MAX,
                      placebo_max: float = PLACEBO_MAX) -> dict:
    """Verdict booléen + justification. `promoted` exige AU MOINS un contrôle mesuré et
    que TOUS les contrôles mesurés passent. Renvoie {promoted, checks, reasons}."""
    checks: dict[str, bool] = {}
    reasons: list[str] = []
    if placebo_p is not None:
        checks["placebo"] = placebo_p < placebo_max
        if not checks["placebo"]:
            reasons.append(f"placebo p={placebo_p} ≥ {placebo_max}")
    if dsr is not None:
        checks["dsr"] = dsr > dsr_min
        if not checks["dsr"]:
            reasons.append(f"DSR {dsr} ≤ {dsr_min}")
    if pbo is not None:
        checks["pbo"] = pbo < pbo_max
        if not checks["pbo"]:
            reasons.append(f"PBO {pbo} ≥ {pbo_max}")
    if edge is not None:
        checks["edge"] = edge > 0
        if not checks["edge"]:
            reasons.append(f"edge net {edge} ≤ 0")
    promoted = bool(checks) and all(checks.values())
    return {"promoted": promoted, "checks": checks, "reasons": reasons}
