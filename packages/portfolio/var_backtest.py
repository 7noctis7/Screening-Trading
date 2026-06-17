"""Backtest de VaR — tests de Kupiec (POF) & Christoffersen (indépendance).

Valider un modèle de VaR = vérifier que la fréquence des dépassements correspond au niveau
théorique (Kupiec) et que ces dépassements ne sont pas groupés (Christoffersen). Régulateur :
backtesting obligatoire (Bâle). stdlib (math), testable hors-ligne.
"""

from __future__ import annotations

import math


def _chi2_sf_df1(x: float) -> float:
    """Fonction de survie du χ² à 1 ddl = erfc(√(x/2)) (p-value)."""
    return math.erfc(math.sqrt(max(0.0, x) / 2.0))


def var_breaches(returns, var: float) -> list[int]:
    """Indicatrice de dépassement : 1 si la perte dépasse la VaR (var = perte positive)."""
    return [1 if r < -abs(var) else 0 for r in returns]


def kupiec_pof(n: int, breaches: int, alpha: float = 0.95) -> dict:
    """Test de couverture inconditionnelle (Proportion Of Failures)."""
    p = 1 - alpha                                   # taux de dépassement théorique
    if n == 0:
        return {"n": 0, "breaches": 0, "lr_stat": 0.0, "p_value": 1.0, "pass": True}
    pi = breaches / n
    eps = 1e-12
    # LR = -2 ln[ (1-p)^(n-x) p^x / (1-π)^(n-x) π^x ]
    ll0 = (n - breaches) * math.log(1 - p) + breaches * math.log(p)
    ll1 = (n - breaches) * math.log(max(1 - pi, eps)) + breaches * math.log(max(pi, eps))
    lr = -2 * (ll0 - ll1)
    pval = _chi2_sf_df1(lr)
    return {"n": n, "breaches": breaches, "expected": round(n * p, 1),
            "breach_rate": round(pi, 4), "lr_stat": round(lr, 3),
            "p_value": round(pval, 4), "pass": pval > 0.05}


def christoffersen_independence(breaches: list[int]) -> dict:
    """Test d'indépendance des dépassements (ne doivent pas se regrouper dans le temps)."""
    n00 = n01 = n10 = n11 = 0
    for a, b in zip(breaches[:-1], breaches[1:]):
        if a == 0 and b == 0: n00 += 1
        elif a == 0 and b == 1: n01 += 1
        elif a == 1 and b == 0: n10 += 1
        else: n11 += 1
    eps = 1e-12
    p01 = n01 / max(1, n00 + n01)
    p11 = n11 / max(1, n10 + n11)
    p = (n01 + n11) / max(1, n00 + n01 + n10 + n11)
    import math
    ll0 = (n00 + n10) * math.log(max(1 - p, eps)) + (n01 + n11) * math.log(max(p, eps))
    ll1 = (n00 * math.log(max(1 - p01, eps)) + n01 * math.log(max(p01, eps))
           + n10 * math.log(max(1 - p11, eps)) + n11 * math.log(max(p11, eps)))
    lr = -2 * (ll0 - ll1)
    return {"lr_stat": round(lr, 3), "p_value": round(_chi2_sf_df1(lr), 4),
            "independent": _chi2_sf_df1(lr) > 0.05}


def backtest_var(returns, var: float, alpha: float = 0.95) -> dict:
    """Backtest complet (Kupiec POF + Christoffersen indépendance) d'un niveau de VaR fixe."""
    b = var_breaches(returns, var)
    pof = kupiec_pof(len(b), sum(b), alpha)
    indep = christoffersen_independence(b)
    return {"var": round(abs(var), 6), "alpha": alpha, **pof,
            "independent": indep["independent"], "indep_p_value": indep["p_value"]}
