"""Kelly fractionnaire pour distributions ASYMÉTRIQUES à queues épaisses.

`kelly_uncertain.py` résout le Kelly BINOMIAL (p, ratio de gain) : deux issues, une seule
perte possible. Les rendements réels ont une queue gauche continue et non bornée ; le Kelly
binomial y surestime systématiquement la mise.

Ici on maximise directement le taux de croissance logarithmique sur la distribution EMPIRIQUE
des rendements par trade, éventuellement enrichie de la queue GPD (`portfolio/evt.py`) :

    f* = argmax_f  E[ ln(1 + f·R) ]            avec f < 1/|pire perte|  (borne de ruine)

Puis on n'utilise qu'une FRACTION lambda de f*, **dérivée d'un budget de drawdown** au lieu
d'être choisie à la main. Pour un mouvement brownien géométrique, une stratégie à la fraction
lambda du Kelly complet touche un jour la fraction b de son pic avec la probabilité

    P(drawdown jusqu'à b·pic) = b ** (2/lambda − 1)

d'où, en inversant :   lambda = 2 / (1 + ln(eps) / ln(b))

Exemples : b=0,50 & eps=1 % → lambda ≈ 0,26 (le « quart de Kelly » classique, enfin DÉRIVÉ) ;
b=0,75 (DD 25 %) & eps=5 % → lambda ≈ 0,17. La formule est gaussienne : elle est OPTIMISTE en
présence de queues épaisses, donc à vérifier par bootstrap par blocs, jamais à prendre seule.

Mandat données réelles : moins de `n_min` observations → UNCALIBRATED, aucune taille renvoyée.
"""

from __future__ import annotations

import math


def growth_rate(f: float, returns) -> float:
    """Taux de croissance logarithmique E[ln(1 + f·R)]. -inf si une issue ruine le compte."""
    total, n = 0.0, 0
    for r in returns:
        x = 1.0 + f * r
        if x <= 1e-12:
            return float("-inf")
        total += math.log(x)
        n += 1
    return total / n if n else float("-inf")


def ruin_bound(returns) -> float:
    """Borne dure : f doit rester < 1/|pire perte| sinon la ruine est atteignable en un coup."""
    worst = min((r for r in returns), default=0.0)
    return float("inf") if worst >= 0 else float(1.0 / abs(worst))


def kelly_empirical(returns, f_hi: float | None = None, tol: float = 1e-4) -> float:
    """f* par recherche par section dorée sur [0, f_hi]. Concave → optimum unique."""
    rs = [float(r) for r in returns if r == r]
    if not rs or max(rs) <= 0:
        return 0.0
    hi = min(f_hi if f_hi is not None else float("inf"), 0.999 * ruin_bound(rs))
    if not math.isfinite(hi) or hi <= 0:
        hi = 10.0
    lo, phi = 0.0, (math.sqrt(5.0) - 1.0) / 2.0
    a, b = lo, hi
    c, d = b - phi * (b - a), a + phi * (b - a)
    while b - a > tol:
        if growth_rate(c, rs) > growth_rate(d, rs):
            b, d = d, c
            c = b - phi * (b - a)
        else:
            a, c = c, d
            d = a + phi * (b - a)
    f = 0.5 * (a + b)
    return float(max(0.0, f if growth_rate(f, rs) > 0 else 0.0))


def lambda_from_drawdown(dd_limit: float, dd_prob: float) -> float:
    """Fraction de Kelly compatible avec « P(drawdown > dd_limit) ≤ dd_prob ».

    dd_limit = 0.25 → on tolère de descendre à b = 0,75 du pic.
    """
    b = 1.0 - float(dd_limit)
    eps = float(dd_prob)
    if not (0.0 < b < 1.0) or not (0.0 < eps < 1.0):
        return 0.0
    lam = 2.0 / (1.0 + math.log(eps) / math.log(b))
    return float(max(0.0, min(1.0, lam)))


def drawdown_probability(lam: float, dd_limit: float) -> float:
    """Réciproque : probabilité de toucher `dd_limit` à la fraction `lam` du Kelly complet."""
    b = 1.0 - float(dd_limit)
    if lam <= 0 or not (0.0 < b < 1.0):
        return 0.0
    return float(min(1.0, b ** (2.0 / lam - 1.0)))


def sized_fraction(returns, dd_limit: float = 0.25, dd_prob: float = 0.05,
                   cap: float = 0.20, n_min: int = 50,
                   tail_losses: list[float] | None = None) -> dict:
    """Taille recommandée = min(lambda(budget DD) · f*, cap). UNCALIBRATED si N < n_min.

    `tail_losses` : pertes simulées depuis la GPD ajustée (`portfolio/evt.py`) à concaténer
    à l'échantillon. Sans elles, le pire cas de l'échantillon borne f* trop haut — « le pire
    est toujours devant ».
    """
    rs = [float(r) for r in returns if r == r]
    n = len(rs)
    if n < n_min:
        return {"available": False, "status": "UNCALIBRATED", "n": n, "n_min": n_min,
                "hint": f"il faut ≥ {n_min} round-trips réels (actuel : {n})"}
    sample = rs + [float(x) for x in (tail_losses or [])]
    f_star = kelly_empirical(sample)
    lam = lambda_from_drawdown(dd_limit, dd_prob)
    f_used = min(lam * f_star, cap)
    return {"available": True, "n": n, "n_tail_added": len(tail_losses or []),
            "f_star": round(f_star, 4), "lambda": round(lam, 4),
            "fraction": round(max(0.0, f_used), 4), "cap": cap,
            "dd_limit": dd_limit, "dd_prob": dd_prob,
            "growth_at_f_used": round(growth_rate(f_used, sample), 6),
            "note": "lambda dérivé d'un budget de drawdown SOUS HYPOTHÈSE BROWNIENNE — "
                    "à confirmer par bootstrap par blocs (queues épaisses = plus risqué)"}
