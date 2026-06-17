"""Scores « grands investisseurs » — Graham, Fisher, Thiel, Schwab (0-100).

Traduit les doctrines en critères mesurables sur les fondamentaux disponibles :
  • **Graham** (L'Investisseur intelligent) : value défensive — rentabilité stable, faible levier,
    PER/PB raisonnables (Graham number), FCF positif.
  • **Fisher** (Actions ordinaires, profits extraordinaires) : qualité-croissance — marges élevées,
    croissance du CA et des bénéfices, ROIC, conversion FCF.
  • **Thiel** (Zero to One) : monopole/moat — marges brutes très élevées (pricing power), ROIC
    dominant, machine à cash (FCF > résultat), faible dette.
  • **Schwab** (4ᵉ révolution industrielle) : exposition thématique (IA, semis, robotique, biotech,
    énergie propre, blockchain, cybersécurité, cloud, espace, VE, fintech).
Pur, testable. NB : approximations (pas de current ratio / dividendes dans le modèle de base).
"""

from __future__ import annotations

from packages.fundamentals import ratios, valuation
from packages.fundamentals.models import Financials

# Secteurs « 4ᵉ révolution industrielle » (cf. thèmes du terminal)
_SCHWAB_CORE = {
    "Intelligence artificielle", "Semi-conducteurs", "Robotique", "Biotech & Génomique",
    "Énergie propre & Transition", "Crypto & Blockchain", "Cybersécurité",
    "Cloud & Datacenters", "Espace & Défense", "Véhicules électriques", "Fintech & Paiements",
}
_SCHWAB_ADJ = {"Communication", "Santé", "Industrie"}


def _pct(n: int, d: int) -> int:
    return round(100 * n / d) if d else 0


def graham_score(f: Financials) -> int:
    per, pb = valuation.per(f), valuation.price_to_book(f)
    checks = [
        f.net_income > 0,                                  # bénéfices positifs
        0 < per < 15,                                      # PER raisonnable
        0 < pb < 1.5,                                      # P/B raisonnable
        0 < per * pb < 22.5,                               # Graham number
        f.total_debt < f.total_equity,                     # faible levier
        f.fcf > 0,                                         # FCF positif
        ratios.net_margin(f) > 0,                          # marge nette positive
    ]
    return _pct(sum(1 for c in checks if c), len(checks))


def fisher_score(f: Financials, prev: Financials | None = None) -> int:
    rev_g = (f.revenue / prev.revenue - 1) if (prev and prev.revenue) else 0.0
    eps_g = (f.net_income / prev.net_income - 1) if (prev and prev.net_income > 0) else 0.0
    checks = [
        ratios.gross_margin(f) > 0.40,                     # pricing power
        ratios.roic(f) > 0.12,                             # création de valeur
        ratios.net_margin(f) > 0.10,                       # marge nette solide
        ratios.fcf_conversion(f) > 0.7,                    # conversion FCF
        rev_g > 0.08,                                      # croissance CA
        eps_g > 0.08,                                      # croissance bénéfices
    ]
    return _pct(sum(1 for c in checks if c), len(checks))


def thiel_score(f: Financials) -> int:
    checks = [
        ratios.gross_margin(f) > 0.60,                     # moat / pricing power fort
        ratios.roic(f) > 0.20,                             # avantage durable
        ratios.net_margin(f) > 0.20,                       # rente
        f.fcf > f.net_income > 0,                          # machine à cash (peu d'accruals)
        ratios.net_debt_to_ebitda(f) < 1.0,               # peu dépendant de la dette
    ]
    return _pct(sum(1 for c in checks if c), len(checks))


def schwab_score(sector: str) -> int:
    if sector in _SCHWAB_CORE:
        return 100
    if sector in _SCHWAB_ADJ:
        return 50
    return 0


def investor_scores(f: Financials, sector: str, prev: Financials | None = None) -> dict:
    g, fi, th, sc = graham_score(f), fisher_score(f, prev), thiel_score(f), schwab_score(sector)
    overall = round((g + fi + th + sc) / 4, 1)
    return {"graham": g, "fisher": fi, "thiel": th, "schwab": sc, "overall": overall}
