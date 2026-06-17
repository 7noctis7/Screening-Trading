"""TCA — Transaction Cost Analysis (best practice buy-side : mesurer le coût d'exécution).

- **Implementation shortfall** : écart entre le prix de décision (arrival) et le prix d'exécution.
- **Décomposition** du coût : spread + impact marché + frais (en points de base et en $).
Pur (stdlib), testable hors-ligne.
"""

from __future__ import annotations


def implementation_shortfall(arrival_price: float, avg_fill_price: float,
                             side: str, notional: float) -> dict:
    """Coût de slippage vs prix d'arrivée. side='buy' → payer plus cher = coût positif."""
    if arrival_price <= 0:
        return {"slippage_bps": 0.0, "cost_usd": 0.0}
    sign = 1.0 if side == "buy" else -1.0
    bps = sign * (avg_fill_price / arrival_price - 1.0) * 1e4
    return {"slippage_bps": round(bps, 2), "cost_usd": round(bps / 1e4 * notional, 2)}


def decompose_cost(notional: float, spread_bps: float = 4.0,
                   impact_bps: float = 3.0, fee_bps: float = 1.0) -> dict:
    """Décompose le coût attendu d'un ordre (demi-spread + impact + frais)."""
    half_spread = spread_bps / 2.0
    total_bps = half_spread + impact_bps + fee_bps
    to_usd = lambda b: round(b / 1e4 * notional, 2)  # noqa: E731
    return {"total_bps": round(total_bps, 2), "total_usd": to_usd(total_bps),
            "spread_usd": to_usd(half_spread), "impact_usd": to_usd(impact_bps),
            "fees_usd": to_usd(fee_bps)}
