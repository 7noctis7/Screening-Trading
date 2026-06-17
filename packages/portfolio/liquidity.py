"""Risque de liquidité — horizon de liquidation & VaR ajustée de la liquidité.

Une position n'est pas liquidable instantanément sans impact. On estime le **nombre de jours**
pour solder chaque position à un taux de participation prudent du volume quotidien (ADV), et la
part du portefeuille « illiquide » (> N jours). Pur, testable.
"""

from __future__ import annotations


def liquidation_days(position_usd: float, adv_usd: float, participation: float = 0.10) -> float:
    """Jours pour liquider une position : valeur / (ADV × participation)."""
    cap = max(0.0, adv_usd) * participation
    return round(position_usd / cap, 2) if cap > 0 else float("inf")


def portfolio_liquidity(positions: list[dict], participation: float = 0.10,
                        illiquid_days: float = 5.0) -> dict:
    """Profil de liquidité du portefeuille.

    Args:
        positions: [{symbol, value, adv}] — valeur en $ et ADV en $.
        participation: part max de l'ADV par jour.
        illiquid_days: seuil au-delà duquel une position est jugée illiquide.
    """
    if not positions:
        return {"available": False}
    total = sum(max(0.0, p.get("value", 0.0)) for p in positions) or 1.0
    rows, illiquid_val, wsum = [], 0.0, 0.0
    for p in positions:
        val = max(0.0, p.get("value", 0.0))
        days = liquidation_days(val, p.get("adv", 0.0), participation)
        rows.append({"symbol": p.get("symbol", ""), "days": days if days != float("inf") else None,
                     "weight": round(val / total, 4)})
        if days == float("inf") or days > illiquid_days:
            illiquid_val += val
        if days != float("inf"):
            wsum += days * val
    rows.sort(key=lambda r: (r["days"] is None, -(r["days"] or 0)))
    return {"available": True, "participation": participation, "illiquid_days": illiquid_days,
            "weighted_days": round(wsum / total, 2),
            "illiquid_pct": round(illiquid_val / total, 4),
            "worst": rows[:8]}


def liquidity_adjusted_var(var: float, half_spread: float, days: float = 1.0) -> float:
    """VaR ajustée de la liquidité = VaR + coût de sortie (demi-spread × √horizon)."""
    return round(abs(var) + abs(half_spread) * (max(1.0, days) ** 0.5), 6)
