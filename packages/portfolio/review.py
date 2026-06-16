"""Revue experte automatisée (CFA / FRM / CPA / CAIA) — ANCRÉE sur les métriques.

Règle absolue : aucun chiffre inventé. Le générateur ne lit QUE les métriques calculées
(passées en entrée) et produit un commentaire + un score de santé + des recommandations
priorisées. Ce n'est PAS un conseil en investissement (cf. garde-fous).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Review:
    health_score: int
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    disclaimer: str = "Analyse fondée sur les métriques calculées. Pas un conseil en investissement."


def expert_review(m: dict) -> Review:
    """`m` agrège : sharpe, sortino, max_drawdown, var_95, cvar_95, beta,
    information_ratio, up_capture, down_capture, p_ruin, gross_exposure, net_exposure."""
    strengths, weaknesses, risks, recos = [], [], [], []
    score = 50.0

    sharpe = m.get("sharpe", 0.0)
    if sharpe >= 1.0:
        strengths.append(f"Rendement ajusté du risque solide (Sharpe {sharpe:.2f}).")
        score += 12
    elif sharpe < 0.3:
        weaknesses.append(f"Rendement ajusté du risque faible (Sharpe {sharpe:.2f}).")
        score -= 10

    dd = m.get("max_drawdown", 0.0)
    if dd <= -0.20:
        weaknesses.append(f"Drawdown maximal élevé ({dd:.0%}).")
        recos.append("Réduire la taille ou resserrer les stops (drawdown > 20%).")
        score -= 12
    elif dd > -0.10:
        strengths.append(f"Drawdown contenu ({dd:.0%}).")
        score += 6

    ir = m.get("information_ratio")
    if ir is not None and ir >= 0.5:
        strengths.append(f"Surperformance régulière vs benchmark (IR {ir:.2f}).")
        score += 6
    elif ir is not None and ir < 0:
        weaknesses.append(f"Sous-performance vs benchmark (IR {ir:.2f}).")

    beta = m.get("beta")
    if beta is not None and beta > 1.2:
        risks.append(f"Sensibilité au marché élevée (beta {beta:.2f}).")
        recos.append("Diversifier ou couvrir pour réduire le beta (> 1.2).")
        score -= 6

    cvar = m.get("cvar_95")
    if cvar and cvar >= 0.03:
        risks.append(f"Risque de queue notable (CVaR 95% {cvar:.1%}).")
        score -= 6

    p_ruin = m.get("p_ruin")
    if p_ruin is not None and p_ruin > 0.05:
        risks.append(f"Probabilité de ruine non négligeable ({p_ruin:.1%} en Monte Carlo).")
        recos.append("Baisser le levier/risque par trade (proba de ruine > 5%).")
        score -= 10

    net, gross = m.get("net_exposure"), m.get("gross_exposure")
    if net is not None and gross and gross > 0 and abs(net) / gross > 0.9:
        risks.append("Exposition très directionnelle (nette ≈ brute).")
        recos.append("Envisager des positions de couverture / market-neutral.")

    if not recos:
        recos.append("Profil équilibré : maintenir la discipline de risque et le suivi du régime.")
    return Review(int(max(0, min(100, round(score)))), strengths, weaknesses, risks, recos)
