"""Turnover & capacité — métriques de trading institutionnelles.

- **Turnover** : volume tradé rapporté au capital, annualisé → mesure le coût de friction
  et la « patience » de la stratégie (un turnover élevé érode l'alpha net).
- **Capacité** : taille de position soutenable sans impact marché excessif, à partir de l'ADV
  (average daily volume) et d'un taux de participation prudent.
Pur, testable hors-ligne.
"""

from __future__ import annotations


def turnover(trades, avg_equity: float, period_days: int) -> dict:
    """Turnover annualisé à partir des trades clôturés.

    Notionnel tradé = Σ(|qty·entry| + |qty·exit|). Annualisé = notionnel/equity × 252/jours.
    """
    closed = [t for t in trades if getattr(t, "exit_price", None) is not None]
    if not closed or avg_equity <= 0 or period_days <= 0:
        return {"annualized": 0.0, "n_round_trips": len(closed), "traded_notional": 0.0}
    notional = sum(abs(t.qty * t.entry_price) + abs(t.qty * (t.exit_price or t.entry_price))
                   for t in closed)
    ann = notional / avg_equity * (252.0 / period_days)
    return {"annualized": round(ann, 3), "n_round_trips": len(closed),
            "traded_notional": round(notional, 2)}


def capacity_estimate(adv_usd: float, participation: float = 0.10,
                      max_weight: float = 0.20) -> dict:
    """Capacité d'une position : min(participation·ADV, plafond de poids).

    Args:
        adv_usd: volume quotidien moyen en $ de l'actif.
        participation: part max de l'ADV qu'on s'autorise (10 % = prudent).
        max_weight: plafond de poids par position (cohérence avec les limites).
    """
    by_liquidity = max(0.0, adv_usd) * participation
    return {"max_position_usd": round(by_liquidity, 2),
            "participation": participation, "max_weight": max_weight}
