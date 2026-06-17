"""Bande de non-trading (rebalance threshold) — réduit le churn (best practice).

Ne génère un ordre que si l'écart |cible − actuel| dépasse une bande. Évite de réarbitrer
en permanence pour des micro-écarts (économie de coûts/slippage). Pur, testable.
"""

from __future__ import annotations


def apply_no_trade_band(target_weights: dict[str, float],
                        current_weights: dict[str, float] | None = None,
                        band: float = 0.02) -> dict:
    """Filtre les ordres dont l'écart au poids cible est sous la bande.

    Returns:
        {orders:[{symbol, target, current, delta}], filtered:int, band}.
    """
    cur = current_weights or {}
    orders: list[dict] = []
    filtered = 0
    for sym, tw in target_weights.items():
        cw = cur.get(sym, 0.0)
        delta = tw - cw
        if abs(delta) >= band:
            orders.append({"symbol": sym, "target": round(tw, 4),
                           "current": round(cw, 4), "delta": round(delta, 4)})
        else:
            filtered += 1
    # sorties : présent en cours mais plus en cible et au-dessus de la bande
    for sym, cw in cur.items():
        if sym not in target_weights and cw >= band:
            orders.append({"symbol": sym, "target": 0.0, "current": round(cw, 4),
                           "delta": round(-cw, 4)})
    return {"orders": orders, "filtered": filtered, "band": band}
