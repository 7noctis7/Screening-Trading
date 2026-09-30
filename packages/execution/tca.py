"""TCA — Transaction Cost Analysis (best practice buy-side : mesurer le coût d'exécution).

- **Implementation shortfall** : écart entre le prix de décision (arrival) et le prix d'exécution.
- **Décomposition** du coût : spread + impact marché + frais (en points de base et en $).
  Quand les paramètres bps historiques sont omis, la décomposition passe par
  `packages.execution.frictions.Frictions` (commission / spread / slippage séparés).
Pur (stdlib + frictions), testable hors-ligne.
"""

from __future__ import annotations

from packages.execution.frictions import Frictions


def implementation_shortfall(arrival_price: float, avg_fill_price: float,
                             side: str, notional: float) -> dict:
    """Coût de slippage vs prix d'arrivée. side='buy' → payer plus cher = coût positif."""
    if arrival_price <= 0:
        return {"slippage_bps": 0.0, "cost_usd": 0.0}
    sign = 1.0 if side == "buy" else -1.0
    bps = sign * (avg_fill_price / arrival_price - 1.0) * 1e4
    return {"slippage_bps": round(bps, 2), "cost_usd": round(bps / 1e4 * notional, 2)}


def decompose_cost(notional: float, spread_bps: float | None = None,
                   impact_bps: float | None = None, fee_bps: float | None = None,
                   *, prix_mid: float = 100.0,
                   frictions: Frictions | None = None) -> dict:
    """Décompose le coût attendu d'un ordre.

    Compatibilité : si `spread_bps` / `impact_bps` / `fee_bps` sont fournis (appelants
    historiques), on garde la formule agrégée en bps. Sinon on délègue à `Frictions.detail`
    — c'est le chemin production (snapshot), qui peuplait auparavant des bps magiques.
    """
    n = max(0.0, float(notional))
    if spread_bps is not None or impact_bps is not None or fee_bps is not None:
        sp = 4.0 if spread_bps is None else float(spread_bps)
        im = 3.0 if impact_bps is None else float(impact_bps)
        fe = 1.0 if fee_bps is None else float(fee_bps)
        half_spread = sp / 2.0
        total_bps = half_spread + im + fe
        to_usd = lambda b: round(b / 1e4 * n, 2)  # noqa: E731
        return {"total_bps": round(total_bps, 2), "total_usd": to_usd(total_bps),
                "spread_usd": to_usd(half_spread), "impact_usd": to_usd(im),
                "fees_usd": to_usd(fe), "source": "bps_legacy"}

    f = frictions or Frictions()
    d = f.detail(n, float(prix_mid))
    total = float(d["total"])
    bps = d["bps_du_notionnel"]
    return {
        "total_bps": bps if bps is not None else 0.0,
        "total_usd": round(total, 2),
        "spread_usd": round(float(d["spread"]), 2),
        "impact_usd": round(float(d["slippage"]), 2),  # glissement ticks ≈ impact
        "fees_usd": round(float(d["commission"]), 2),
        "frictions": d,
        "source": "frictions",
    }
