"""F-score qualité (inspiré Piotroski) — version statique sur données point-in-time.

Piotroski strict requiert les variations annuelles ; ici on évalue 9 critères de **solidité
financière** sur les fondamentaux disponibles (rentabilité, qualité des résultats, levier,
marges). Score 0-9 (haut = solide). Pur, testable.
"""

from __future__ import annotations

from packages.fundamentals import ratios, valuation
from packages.fundamentals.models import Financials


def f_score(f: Financials) -> int:
    """Score de solidité 0-9 (proxy Piotroski statique)."""
    nd_ebitda = ratios.net_debt_to_ebitda(f)
    checks = [
        f.net_income > 0,                          # rentable
        f.fcf > 0,                                 # cash-flow positif
        ratios.roe(f) > 0,                         # ROE positif
        f.fcf >= f.net_income,                     # qualité des résultats (peu d'accruals)
        ratios.gross_margin(f) > 0.30,             # pricing power
        ratios.ebit_margin(f) > 0.10,              # marge opérationnelle saine
        ratios.roic(f) > 0.10,                     # création de valeur > coût du capital
        nd_ebitda < 3.0,                           # levier maîtrisé
        ratios.interest_coverage(f) > 3.0,         # service de la dette confortable
    ]
    return int(sum(1 for c in checks if c))


def f_score_label(score: int) -> str:
    return "solide" if score >= 7 else ("moyen" if score >= 4 else "fragile")
