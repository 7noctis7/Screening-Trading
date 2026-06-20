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


def _assets(f: Financials) -> float:
    return max(1e-9, f.total_equity + f.total_debt)


def altman_z(f: Financials) -> dict:
    """Score Z d'Altman (risque de faillite) — version approchée sur fondamentaux disponibles.

    Z = 1.2·X1 + 1.4·X2 + 3.3·X3 + 0.6·X4 + 1.0·X5
    (X1≈cash/actif, X2≈capitaux propres/actif [proxy bénéfices non distribués],
     X3=EBIT/actif, X4=capitalisation/dette, X5=CA/actif). Z>2.99 sûr · <1.81 détresse.

    Garde-fous : sans bilan exploitable (ETF, données absentes) → N/A ; X4 est BORNÉ (sinon une
    dette ≈ 0 fait exploser le ratio vers l'infini) ; Z final borné à une plage réaliste.
    """
    ta = f.total_equity + f.total_debt
    if ta <= 0 or f.revenue <= 0:                 # pas de bilan/CA exploitable (ETF, champs absents)
        return {"z": None, "zone": "n/a"}
    x1 = f.cash / ta
    x2 = f.total_equity / ta
    x3 = f.ebit / ta
    # X4 = capitalisation / dette : peu/pas de dette = très sûr, mais on BORNE (évite l'explosion).
    x4 = min(6.0, (f.price * f.shares) / f.total_debt) if f.total_debt > 1.0 else 6.0
    x5 = f.revenue / ta
    z = 1.2 * x1 + 1.4 * x2 + 3.3 * x3 + 0.6 * x4 + 1.0 * x5
    z = max(-20.0, min(30.0, z))                  # plage réaliste (jamais 1e19)
    zone = "sûr" if z > 2.99 else ("gris" if z >= 1.81 else "détresse")
    return {"z": round(z, 2), "zone": zone}


def piotroski_full(curr: Financials, prev: Financials) -> int:
    """Piotroski F-score complet (0-9) avec variations annuelles (curr vs prev)."""
    roa_c = curr.net_income / _assets(curr)
    roa_p = prev.net_income / _assets(prev)
    checks = [
        curr.net_income > 0,                                   # 1. ROA positif
        curr.fcf > 0,                                          # 2. CFO positif
        roa_c > roa_p,                                         # 3. ΔROA > 0
        curr.fcf > curr.net_income,                            # 4. CFO > résultat net (accruals)
        (curr.total_debt / _assets(curr)) < (prev.total_debt / _assets(prev)),  # 5. levier ↓
        (curr.cash / _assets(curr)) > (prev.cash / _assets(prev)),              # 6. liquidité ↑
        curr.shares <= prev.shares * 1.001,                   # 7. pas de dilution
        (curr.gross_profit / curr.revenue) > (prev.gross_profit / prev.revenue),  # 8. marge ↑
        (curr.revenue / _assets(curr)) > (prev.revenue / _assets(prev)),        # 9. rotation ↑
    ]
    return int(sum(1 for c in checks if c))
