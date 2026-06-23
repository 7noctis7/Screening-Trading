"""Maîtrise statistique des procédés (SPC / Six Sigma) — qualité data, 0 dépendance.

- `p_chart()` : proportion de défauts + limites de contrôle 3σ (carte p de Shewhart).
- `cusum()` : détection de dérive de niveau (shift) — plus sensible qu'une carte p.
- `dpmo()` / `sigma_level()` : positionnement Six Sigma (cible 3,4 DPMO ≈ 6σ, convention
  du décalage 1,5σ de Motorola).
stdlib (math/statistics), testable hors-ligne.
"""

from __future__ import annotations

import math
import statistics


def _norm_ppf(p: float) -> float:
    """Quantile normal (approx. Acklam), p ∈ (0,1)."""
    p = min(1 - 1e-12, max(1e-12, p))
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    plow, phigh = 0.02425, 1 - 0.02425
    if p < plow:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
               ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    if p > phigh:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
               ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    q = p - 0.5
    r = q * q
    return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / \
           (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)


def p_chart(defects: int, n: int) -> dict:
    """Carte p : proportion p̂=d/n et limites de contrôle ±3σ (σ=√(p(1-p)/n))."""
    if n <= 0:
        return {"available": False}
    p = defects / n
    sigma = math.sqrt(max(p * (1 - p), 0.0) / n)
    return {
        "available": True, "n": n, "defects": defects, "p": round(p, 8),
        "ucl": round(min(1.0, p + 3 * sigma), 8),
        "lcl": round(max(0.0, p - 3 * sigma), 8),
    }


def cusum(values: list[float], target: float, k: float = 0.5, h: float = 5.0) -> dict:
    """CUSUM tabulaire standardisé (en unités σ). Alarme si S⁺ ou S⁻ dépasse `h`.
    `k` = demi-amplitude à détecter (σ) ; `h` = seuil de décision (typiquement 4-5σ)."""
    if len(values) < 2:
        return {"available": False}
    sd = statistics.pstdev(values) or 1.0
    sp = sn = 0.0
    alarms: list[int] = []
    for i, x in enumerate(values):
        z = (x - target) / sd
        sp = max(0.0, sp + z - k)
        sn = max(0.0, sn - z - k)
        if sp > h or sn > h:
            alarms.append(i)
    return {"available": True, "alarms": alarms, "n_alarms": len(alarms),
            "s_pos_last": round(sp, 3), "s_neg_last": round(sn, 3), "k": k, "h": h}


def dpmo(defects: int, units: int, opportunities_per_unit: int = 1) -> float:
    """Défauts par million d'opportunités."""
    opp = units * opportunities_per_unit
    return defects / opp * 1_000_000 if opp > 0 else 0.0


def sigma_level(dpmo_value: float) -> float:
    """Niveau sigma (convention du décalage 1,5σ) : z = Φ⁻¹(rendement) + 1,5.
    3,4 DPMO → 6σ ; ~66 800 DPMO → ~3σ."""
    yld = 1.0 - min(max(dpmo_value, 0.0), 1_000_000.0) / 1_000_000.0
    if yld >= 1.0:
        return 6.0
    if yld <= 0.0:
        return 0.0
    return round(_norm_ppf(yld) + 1.5, 2)
