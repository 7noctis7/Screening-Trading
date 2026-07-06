"""Coûts d'exécution RÉELS mesurés depuis le journal — calibre le sabotage avec du vécu.

Le sabotage-gate stresse aujourd'hui avec des coûts ARBITRAIRES (coût×3). Dès que le
journal accumule des round-trips, on peut mesurer le slippage RÉEL décision→fill :
  slippage_bps = (prix de fill / prix de DÉCISION − 1) × 10 000   (achat ; signe conservé)

Sources 100 % factuelles : `decision_price` figé dans `features_snapshot` à la décision
(run_live, 2026-07-06) et `entry_price` = fill broker. Mandat données réelles
(CLAUDE.md) : N < `min_n` → **UNCALIBRATED**, on ne recommande RIEN.
"""

from __future__ import annotations


def measured_slippage(journal, *, min_n: int = 20) -> dict:
    """Statistiques de slippage réel (bps) sur les trades `legacy=0` porteurs des 2 prix.

    Returns:
        {available, n, median_bps, mean_bps, p90_bps, worst_bps} ou
        {available: False, status: "UNCALIBRATED", n} si l'échantillon est insuffisant.
    """
    obs: list[float] = []
    for t in journal.all(legacy=False):
        dp = (t.features_snapshot or {}).get("decision_price")
        if dp and dp > 0 and t.entry_price > 0:
            obs.append((t.entry_price / dp - 1.0) * 10_000)
    n = len(obs)
    if n < min_n:
        return {"available": False, "status": "UNCALIBRATED", "n": n, "min_n": min_n,
                "hint": f"il faut ≥ {min_n} fills avec decision_price (actuel : {n})"}
    obs.sort()
    mean = sum(obs) / n
    return {"available": True, "n": n,
            "median_bps": round(obs[n // 2], 2),
            "mean_bps": round(mean, 2),
            "p90_bps": round(obs[min(n - 1, int(0.9 * n))], 2),
            "worst_bps": round(obs[-1], 2)}


def sabotage_cost_bps(journal, *, min_n: int = 20, floor_bps: float = 10.0) -> float | None:
    """Coût de stress pour le sabotage-gate : le P90 MESURÉ (jamais < floor_bps).

    None si UNCALIBRATED → l'appelant garde son stress arbitraire (coût×3) et le DIT."""
    st = measured_slippage(journal, min_n=min_n)
    if not st.get("available"):
        return None
    return max(floor_bps, abs(st["p90_bps"]))
