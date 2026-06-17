"""Réconciliation portefeuille cible ↔ positions réelles (best practice ops d'exécution).

Compare l'allocation cible (poids du modèle) aux positions effectives chez le broker et produit
les ordres d'ajustement (achat/vente), le drift agrégé et le taux d'exécution. Pur, testable.
"""

from __future__ import annotations


def reconcile(target_weights: dict[str, float], current_values: dict[str, float],
              equity: float, min_order: float = 1.0) -> dict:
    """Ordres d'ajustement pour passer des positions actuelles à l'allocation cible.

    Args:
        target_weights: poids cibles (fraction du portefeuille).
        current_values: valeur $ par position détenue.
        equity: capital total de référence.
        min_order: montant minimal d'ordre (ignore la poussière).
    """
    symbols = set(target_weights) | set(current_values)
    orders, drift = [], 0.0
    for s in symbols:
        tgt = target_weights.get(s, 0.0) * equity
        cur = current_values.get(s, 0.0)
        delta = tgt - cur
        drift += abs(delta)
        if abs(delta) >= min_order:
            orders.append({"symbol": s, "side": "buy" if delta > 0 else "sell",
                           "delta_usd": round(delta, 2), "target_usd": round(tgt, 2),
                           "current_usd": round(cur, 2)})
    orders.sort(key=lambda o: -abs(o["delta_usd"]))
    return {"orders": orders, "n_orders": len(orders),
            "drift_usd": round(drift, 2),
            "drift_pct": round(drift / equity, 4) if equity else 0.0}


def fill_rate(submitted: int, filled: int) -> dict:
    """Taux d'exécution (qualité d'exécution)."""
    return {"submitted": submitted, "filled": filled,
            "fill_rate": round(filled / submitted, 4) if submitted else 0.0}
