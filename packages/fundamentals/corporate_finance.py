"""Finance d'entreprise — cadre Vernimmen (rentabilité économique, levier) + Damodaran (coût du
capital, valorisation par scénarios). Pur, déterministe, testable. Aucune dépendance.

Vernimmen : ROCE après impôt vs WACC = création de valeur ; EVA (profit économique) ; DuPont
(décomposition de la ROE) ; gearing (dette nette / capitaux propres).
Damodaran : coût des fonds propres par le MEDAF (CAPM), WACC, DCF FCFF par scénarios
(bear/base/bull), DCF inversé (croissance implicite dans le cours)."""

from __future__ import annotations

from packages.fundamentals.models import Financials

_TAX = 0.25          # taux par défaut, si la juridiction est inconnue (cf. taux_impot)
_RF = 0.04           # taux sans risque (≈ 10Y US) — surchargé par l'appelant si dispo
_ERP = 0.05          # prime de risque actions (Damodaran ~4.5-5.5 %)

# PLAFOND DE CROISSANCE PERPÉTUELLE. Aucune entreprise ne croît indéfiniment plus vite que
# l'économie qui la contient : au-delà, elle finirait par la représenter en entier. Le plafond
# est donc une contrainte ÉCONOMIQUE, pas un réglage — d'où son application à l'intérieur du
# calcul et non dans une signature que l'appelant peut contourner.
#
# L'enjeu n'est pas cosmétique : la valeur terminale pèse 60 à 80 % d'un DCF à dix ans. Avec un
# WACC de 9 %, passer g de 2,5 % à 5 % multiplie le multiple terminal par 1,6.
MAX_CROISSANCE_PERPETUELLE = 0.03

# Taux d'impôt sur les sociétés par juridiction, approchés par la DEVISE DES ÉTATS FINANCIERS
# (meilleur indicateur de domiciliation disponible dans le modèle). Un taux unique appliqué à
# ASML (Pays-Bas), TSM (Taïwan) et aux valeurs américaines biaise le NOPAT, donc le ROCE, donc
# le classement transversal — dans le sens du différentiel de taux, pas au hasard.
_TAUX_PAR_DEVISE = {
    "USD": 0.25,   # fédéral 21 % + états
    "EUR": 0.26,   # moyenne zone euro
    "GBP": 0.25,
    "CHF": 0.15,
    "JPY": 0.30,
    "TWD": 0.20,
    "KRW": 0.24,
    "CNY": 0.25,
    "HKD": 0.17,
    "CAD": 0.26,
    "SEK": 0.21,
    "DKK": 0.22,
    "NOK": 0.22,
    "AUD": 0.30,
    "INR": 0.25,
    "BRL": 0.34,
}


def taux_impot(f: Financials) -> float:
    """Taux d'impôt applicable, approché par la devise des états financiers.

    Devise inconnue ou absente → taux par défaut. On ne devine pas une juridiction : mieux vaut
    un taux moyen assumé qu'un taux précis attribué au mauvais pays.
    """
    dev = (f.currency or f.price_currency or "").strip().upper()
    return _TAUX_PAR_DEVISE.get(dev, _TAX)


def _safe(n: float, d: float) -> float:
    return n / d if d else float("nan")


def convert_financials(f: Financials, fx: float) -> Financials:
    """Convertit les grandeurs MONÉTAIRES des états financiers par le taux `fx` (1 devise comptes =
    `fx` devise du cours) → cohérence avec le cours/capitalisation. Le cours et le nombre d'actions
    NE sont PAS touchés (déjà dans la devise du cours). Pur, déterministe."""
    from dataclasses import replace
    if not fx or fx <= 0 or fx == 1.0:
        return f
    return replace(
        f, revenue=f.revenue * fx, gross_profit=f.gross_profit * fx, ebit=f.ebit * fx,
        ebitda=f.ebitda * fx, net_income=f.net_income * fx, total_equity=f.total_equity * fx,
        total_debt=f.total_debt * fx, cash=f.cash * fx, fcf=f.fcf * fx,
        interest_expense=f.interest_expense * fx, currency=f.price_currency or f.currency)


def capital_employed(f: Financials, precedent: Financials | None = None) -> float:
    """Capitaux employés (Vernimmen) = capitaux propres + dette nette.

    `precedent` fourni → MOYENNE des deux bilans. La date de clôture n'est pas un instant neutre :
    la plupart des sociétés la placent APRÈS leur pic d'activité, stocks écoulés et créances
    encaissées, donc dette nette au plancher annuel. Prendre cette seule photo sous-estime les
    capitaux employés et surestime d'autant la rentabilité — un distributeur qui clôture en
    janvier peut afficher un ROCE de 18 % là où la moyenne annuelle en donnerait 11.

    Sans période précédente, on calcule sur la clôture seule : c'est ce que la source fournit.
    `base_capitaux_employes()` dit laquelle des deux bases a servi, pour que le chiffre ne soit
    jamais lu comme plus solide qu'il ne l'est.
    """
    ce = f.total_equity + max(0.0, f.total_debt - f.cash)
    if precedent is None:
        return ce
    ce_prec = precedent.total_equity + max(0.0, precedent.total_debt - precedent.cash)
    return (ce + ce_prec) / 2.0


def base_capitaux_employes(precedent: Financials | None) -> str:
    """« moyenne » ou « clôture » — la base réellement utilisée, à afficher avec le ratio."""
    return "moyenne" if precedent is not None else "clôture"


def roce_after_tax(f: Financials, precedent: Financials | None = None) -> float:
    """Rentabilité des capitaux employés, après impôt : NOPAT / capitaux employés.

    Impôt par juridiction (cf. `taux_impot`) et capitaux employés moyens si la période
    précédente est disponible — les deux corrigent un biais systématique, pas du bruit.
    """
    return _safe(f.ebit * (1 - taux_impot(f)), capital_employed(f, precedent))


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
    # Le plafond s'applique ICI, pas dans la signature : une contrainte économique n'a pas à
    # être négociable par l'appelant. Le garde-fou `wacc <= g` seul n'attrape que l'absurde
    # (valeur infinie), jamais le simplement trop optimiste — qui est le cas dangereux.
    tg = min(float(terminal_growth), MAX_CROISSANCE_PERPETUELLE)
    if f.fcf <= 0 or wacc_rate <= tg or f.shares <= 0:
        return float("nan")
    pv, cf = 0.0, f.fcf
    for t in range(1, years + 1):
        cf *= (1 + growth)
        pv += cf / (1 + wacc_rate) ** t
    terminal = cf * (1 + tg) / (wacc_rate - tg)
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
            # On publie la croissance EFFECTIVEMENT utilisée, pas celle demandée : sinon le
            # payload annoncerait une hypothèse que le calcul n'a pas retenue.
            "wacc": round(wacc_rate, 4),
            "terminal_growth": min(float(terminal_growth), MAX_CROISSANCE_PERPETUELLE),
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
