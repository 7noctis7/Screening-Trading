"""Finance d'entreprise — cadre Vernimmen (rentabilité économique, levier) + Damodaran (coût du
capital, valorisation par scénarios). Pur, déterministe, testable. Aucune dépendance.

Vernimmen : ROCE après impôt vs WACC = création de valeur ; EVA (profit économique) ; DuPont
(décomposition de la ROE) ; gearing (dette nette / capitaux propres).
Damodaran : coût des fonds propres par le MEDAF (CAPM), WACC, DCF FCFF par scénarios
(bear/base/bull), DCF inversé (croissance implicite dans le cours)."""

from __future__ import annotations

from packages.fundamentals.models import Financials

_TAX = 0.25
_RF = 0.04           # taux sans risque (≈ 10Y US) — surchargé par l'appelant si dispo
_ERP = 0.05          # prime de risque actions (Damodaran ~4.5-5.5 %)


def _safe(n: float, d: float) -> float:
    return n / d if d else float("nan")


def capital_employed(f: Financials) -> float:
    """Capitaux employés (Vernimmen) = capitaux propres + dette nette."""
    return f.total_equity + max(0.0, f.total_debt - f.cash)


def roce_after_tax(f: Financials) -> float:
    """Rentabilité des capitaux employés, après impôt : NOPAT / capitaux employés."""
    return _safe(f.ebit * (1 - _TAX), capital_employed(f))


def cost_of_equity(beta: float, rf: float = _RF, erp: float = _ERP) -> float:
    """Coût des fonds propres par le MEDAF (CAPM) : rf + β·prime de risque actions."""
    return rf + max(0.0, beta) * erp


def cost_of_debt(f: Financials, tax: float = _TAX) -> float:
    """Coût de la dette après impôt : charges d'intérêts / dette, net d'IS. Défaut prudent si N/A."""
    if f.total_debt > 1.0 and f.interest_expense > 0:
        return (f.interest_expense / f.total_debt) * (1 - tax)
    return 0.04 * (1 - tax)


def wacc(f: Financials, beta: float = 1.0, rf: float = _RF, erp: float = _ERP,
         tax: float = _TAX) -> float:
    """Coût moyen pondéré du capital (Damodaran) : pondération valeur de marché des fonds propres
    et de la dette. Borné à un plancher réaliste (≥ 5 %) pour éviter un DCF dégénéré."""
    e = max(0.0, f.price * f.shares)
    d = max(0.0, f.total_debt)
    v = e + d
    if v <= 0:
        return max(0.06, cost_of_equity(beta, rf, erp))
    ke = cost_of_equity(beta, rf, erp)
    kd = cost_of_debt(f, tax)
    w = (e / v) * ke + (d / v) * kd
    return max(0.05, min(0.20, w))


def eva(f: Financials, wacc_rate: float) -> float:
    """Profit économique (EVA) = (ROCE − WACC) × capitaux employés. >0 = création de valeur."""
    ce = capital_employed(f)
    r = roce_after_tax(f)
    if ce <= 0 or r != r:
        return float("nan")
    return (r - wacc_rate) * ce


def dupont(f: Financials) -> dict[str, float]:
    """Décomposition DuPont de la ROE = marge nette × rotation de l'actif × levier financier.
    Actif total approché = capitaux propres + dette (cohérent avec le reste du projet)."""
    assets = max(1e-9, f.total_equity + f.total_debt)
    net_margin = _safe(f.net_income, f.revenue)
    asset_turnover = _safe(f.revenue, assets)
    leverage = _safe(assets, f.total_equity)
    roe = net_margin * asset_turnover * leverage
    return {"net_margin": net_margin, "asset_turnover": asset_turnover,
            "equity_multiplier": leverage, "roe": roe}


def gearing(f: Financials) -> float:
    """Gearing = dette nette / capitaux propres (Vernimmen). Négatif = trésorerie nette positive."""
    return _safe(f.total_debt - f.cash, f.total_equity)


def _dcf(f: Financials, wacc_rate: float, growth: float, terminal_growth: float = 0.025,
         years: int = 10) -> float:
    """DCF FCFF → valeur intrinsèque par action (cœur partagé par les scénarios)."""
    if f.fcf <= 0 or wacc_rate <= terminal_growth or f.shares <= 0:
        return float("nan")
    pv, cf = 0.0, f.fcf
    for t in range(1, years + 1):
        cf *= (1 + growth)
        pv += cf / (1 + wacc_rate) ** t
    terminal = cf * (1 + terminal_growth) / (wacc_rate - terminal_growth)
    pv += terminal / (1 + wacc_rate) ** years
    equity_value = pv - (f.total_debt - f.cash)
    return equity_value / f.shares


def damodaran_scenarios(f: Financials, wacc_rate: float, base_growth: float = 0.06,
                        terminal_growth: float = 0.025, years: int = 10) -> dict:
    """Valorisation DCF par scénarios (Damodaran : 'a story for every number').
    bear/base/bull = croissance base ∓ 4 pts. Renvoie les valeurs intrinsèques + marge de sécurité."""
    g = max(-0.05, min(0.30, base_growth))
    scen = {"bear": max(-0.05, g - 0.04), "base": g, "bull": g + 0.04}
    out: dict[str, float] = {}
    for name, gr in scen.items():
        out[name] = round(_dcf(f, wacc_rate, gr, terminal_growth, years), 2)
    base_val = out.get("base")
    mos = (base_val / f.price - 1.0) if (base_val == base_val and f.price) else float("nan")
    return {"scenarios": out, "growth_assumptions": {k: round(v, 4) for k, v in scen.items()},
            "wacc": round(wacc_rate, 4), "terminal_growth": terminal_growth,
            "intrinsic_base": base_val, "margin_of_safety": round(mos, 4) if mos == mos else None}


def reverse_dcf_growth(f: Financials, wacc_rate: float, terminal_growth: float = 0.025,
                       years: int = 10) -> float:
    """DCF INVERSÉ (Damodaran/Mauboussin) : taux de croissance du FCF implicite dans le cours actuel.
    Répond à 'qu'est-ce que le marché price ?'. Recherche dichotomique. NaN si non résoluble."""
    if f.fcf <= 0 or f.price <= 0 or f.shares <= 0:
        return float("nan")
    lo, hi = -0.20, 0.60
    target = f.price
    for _ in range(60):
        mid = (lo + hi) / 2
        val = _dcf(f, wacc_rate, mid, terminal_growth, years)
        if val != val:
            return float("nan")
        if val < target:
            lo = mid
        else:
            hi = mid
    return round((lo + hi) / 2, 4)
