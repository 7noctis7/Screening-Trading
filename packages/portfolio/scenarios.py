"""Stress-tests macro & couverture (hedging) — analyse de scénarios institutionnelle.

Inspiré des pratiques buy-side (skfolio/Riskfolio/pyfolio) : on choque le portefeuille par
**classe d'actifs** selon des scénarios macro historiques/hypothétiques, et on en déduit une
**suggestion de couverture** (short indiciel) pour ramener la perte au pire scénario sous une
limite cible. Pur (numpy/stdlib), testable hors-ligne.
"""

from __future__ import annotations

# Chocs par classe d'actifs (rendement instantané). Sources : épisodes de marché types.
SCENARIOS: dict[str, dict[str, float]] = {
    "Krach actions (type 2008)": {"equity": -0.45, "etf": -0.40, "index": -0.45,
                                  "crypto": -0.55, "commodity": -0.30, "forex": 0.0},
    "Choc COVID (mars 2020)": {"equity": -0.34, "etf": -0.30, "index": -0.34,
                               "crypto": -0.40, "commodity": -0.25, "forex": 0.0},
    "Choc de taux (+200 bp)": {"equity": -0.12, "etf": -0.10, "index": -0.12,
                               "crypto": -0.18, "commodity": -0.05, "forex": 0.02},
    "Risk-off / fuite qualité": {"equity": -0.10, "etf": -0.08, "index": -0.10,
                                 "crypto": -0.22, "commodity": -0.06, "forex": 0.03},
    "Inflation / flambée pétrole": {"equity": -0.08, "etf": -0.06, "index": -0.08,
                                    "crypto": -0.12, "commodity": 0.20, "forex": 0.0},
    "Rallye risk-on": {"equity": 0.12, "etf": 0.10, "index": 0.12,
                       "crypto": 0.28, "commodity": 0.05, "forex": 0.0},
}


def scenario_analysis(weights_by_class: dict[str, float],
                      scenarios: dict[str, dict[str, float]] | None = None) -> list[dict]:
    """P&L estimé du portefeuille par scénario (Σ poids_classe × choc_classe)."""
    scen = scenarios or SCENARIOS
    out: list[dict] = []
    for name, shocks in scen.items():
        pnl = sum(w * shocks.get(ac, 0.0) for ac, w in weights_by_class.items())
        worst_ac = min(weights_by_class, key=lambda ac: weights_by_class[ac] * shocks.get(ac, 0.0),
                       default="—") if weights_by_class else "—"
        out.append({"name": name, "pnl_pct": round(pnl, 4), "worst_class": worst_ac})
    return sorted(out, key=lambda d: d["pnl_pct"])      # du pire au meilleur


def hedge_suggestion(weights_by_class: dict[str, float], target_max_loss: float = -0.15,
                     scenarios: dict[str, dict[str, float]] | None = None) -> dict:
    """Couverture suggérée pour ramener la perte du PIRE scénario sous `target_max_loss`.

    Hedge = short indiciel proportionnel à l'exposition « equity-like » (equity+etf+index).
    Renvoie {worst_scenario, worst_pnl_pct, needed:bool, hedge_pct, rationale}.
    """
    res = scenario_analysis(weights_by_class, scenarios)
    worst = res[0] if res else {"name": "—", "pnl_pct": 0.0}
    eq_like = sum(weights_by_class.get(k, 0.0) for k in ("equity", "etf", "index"))
    needed = worst["pnl_pct"] < target_max_loss and eq_like > 0
    hedge_pct = 0.0
    if needed:
        # part de l'exposition actions à neutraliser pour atteindre la cible
        excess = abs(worst["pnl_pct"]) - abs(target_max_loss)
        hedge_pct = round(min(1.0, excess / abs(worst["pnl_pct"])) * eq_like, 4)
    return {"worst_scenario": worst["name"], "worst_pnl_pct": worst["pnl_pct"],
            "target_max_loss": target_max_loss, "equity_like_exposure": round(eq_like, 4),
            "needed": needed, "hedge_pct": hedge_pct,
            "rationale": ("Short indiciel (ex. SPY/ES) pour réduire le bêta actions"
                          if needed else "Pas de couverture requise au seuil cible")}
