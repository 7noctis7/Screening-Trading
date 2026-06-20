"""Note d'analyse fondamentale par société — qualité institutionnelle, sources gratuites.

Assemble en une structure unique : identité, audit PwC des intrants financiers (fiabilité /
cohérence), analyse Vernimmen (ROCE vs WACC, EVA, DuPont, gearing), valorisation Damodaran
(coût du capital MEDAF, DCF par scénarios, DCF inversé, multiples vs secteur), qualité (Piotroski,
Altman Z, scores investisseurs Graham/Fisher/Thiel), et un verdict synthétique.

Provider-agnostique : prend un `Financials` (déjà collecté via la chaîne yfinance→FMP→SEC EDGAR).
Pur, déterministe, testable hors-ligne. Le rendu HTML/PDF est séparé (company_report_render.py)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from packages.fundamentals import corporate_finance as cf
from packages.fundamentals import ratios, scoring, valuation
from packages.fundamentals.investor_scores import investor_scores
from packages.fundamentals.models import Financials


def _f(x: float | None, nd: int = 2) -> float | None:
    if x is None or x != x:                     # None ou NaN
        return None
    return round(float(x), nd)


# ───────────────────────────── AUDIT PwC des intrants ─────────────────────────────
def audit_financials(f: Financials) -> dict[str, Any]:
    """Contrôle de cohérence/fiabilité des données financières (esprit PwC) AVANT toute analyse.
    Sépare critiques (bloquent la fiabilité) / majeures / avertissements. Renvoie un verdict."""
    crit, major, warn = [], [], []
    if f.revenue <= 0:
        crit.append("chiffre d'affaires ≤ 0 (donnée manquante ou erronée)")
    if f.shares <= 0:
        crit.append("nombre d'actions ≤ 0")
    if f.price <= 0:
        crit.append("cours ≤ 0")
    # ordre des marges : CA ≥ marge brute ≥ EBIT ; EBITDA ≥ EBIT
    if f.revenue > 0:
        if f.gross_profit > f.revenue * 1.01:
            major.append("marge brute > chiffre d'affaires (incohérent)")
        if f.ebit > f.gross_profit * 1.02 and f.gross_profit > 0:
            major.append("EBIT > marge brute (incohérent)")
        if f.ebitda + 1 < f.ebit:
            major.append("EBITDA < EBIT (D&A négatif : incohérent)")
        nm = f.net_income / f.revenue
        if not -1.5 <= nm <= 1.0:
            major.append(f"marge nette hors plage plausible ({nm*100:.0f}%)")
        gm = f.gross_profit / f.revenue
        if not -0.05 <= gm <= 1.05:
            warn.append(f"marge brute atypique ({gm*100:.0f}%)")
    if f.total_equity < 0:
        warn.append("capitaux propres négatifs (rachats massifs ou pertes cumulées)")
    if f.cash < 0:
        major.append("trésorerie négative (incohérent)")
    # COMPLÉTUDE (PwC) : signale les champs clés absents (=0) de la source plutôt que de fabriquer
    for label, val in (("EBIT", f.ebit), ("EBITDA", f.ebitda), ("FCF", f.fcf),
                       ("capitaux propres", f.total_equity)):
        if val == 0:
            warn.append(f"{label} absent de la source (analyse partielle — non fabriqué)")
    # qualité des résultats : FCF très éloigné du résultat net
    if f.net_income > 0 and f.fcf < 0:
        warn.append("FCF négatif alors que résultat net positif (accruals à surveiller)")
    # plausibilité du P/S (capi vs CA) — repère les unités erronées
    if f.revenue > 0:
        ps = (f.price * f.shares) / f.revenue
        if ps > 100:
            warn.append(f"P/S extrême ({ps:.0f}) — vérifier les unités (actions/CA)")
    counts = {"critical": len(crit), "major": len(major), "warning": len(warn)}
    ok = len(crit) == 0
    reliability = ("fiable" if ok and not major else
                   "à vérifier" if ok else "non fiable")
    return {"ok": ok, "reliability": reliability, "counts": counts,
            "findings": [{"severity": "critical", "detail": d} for d in crit]
                      + [{"severity": "major", "detail": d} for d in major]
                      + [{"severity": "warning", "detail": d} for d in warn]}


# ───────────────────────────── construction de la note ─────────────────────────────
def technical_score(t: dict[str, Any] | None) -> int | None:
    """Score technique 0-100 à partir du résumé (tendance, RSI, MACD, position vs moyennes mobiles).
    None si pas de données techniques. Borné, robuste aux champs absents."""
    if not t:
        return None
    s = 50.0
    trend = str(t.get("trend") or "")
    s += {"haussière": 18, "baissière": -18}.get(trend, 0)
    if t.get("macd_signal") == "haussier":
        s += 8
    elif t.get("macd_signal") == "baissier":
        s -= 8
    rsi = t.get("rsi")
    if rsi is not None:
        if rsi > 70:
            s -= 6                                  # suracheté
        elif rsi < 30:
            s += 6                                  # survendu (rebond potentiel)
        elif 45 <= rsi <= 60:
            s += 4                                  # zone saine
    for k, wt in (("vs_sma50", 10), ("vs_sma200", 10)):
        v = t.get(k)
        if v is not None:
            s += wt if v > 0 else -wt
    return int(max(0, min(100, round(s))))


def build_company_report(f: Financials, *, name: str | None = None,
                         prior: Financials | None = None, beta: float = 1.0,
                         rf: float = 0.04, erp: float = 0.05,
                         sector_medians: dict[str, float] | None = None,
                         base_growth: float | None = None,
                         technical: dict[str, Any] | None = None,
                         macro: dict[str, Any] | None = None,
                         earnings: dict[str, Any] | None = None,
                         ml_score: float | None = None,
                         price_series: list[float] | None = None,
                         financial_history: list[dict] | None = None) -> dict[str, Any]:
    """Construit la note d'analyse complète (dict sérialisable JSON) pour une société.

    Sections optionnelles à forte valeur (rendues si fournies) :
      - `technical` : tendance, RSI, MACD, position vs moyennes mobiles, plage 52 sem.
      - `macro` : régime de marché, VIX, taux — contexte top-down.
      - `earnings` : prochaine date de résultats, BPA/revenu estimés & annoncés, surprise."""
    sm = sector_medians or {}
    audit = audit_financials(f)

    # croissance de référence pour le DCF : croissance CA réelle si dispo, sinon prudente
    g = base_growth
    if g is None:
        g = f.revenue_growth if f.revenue_growth is not None else 0.06
    g = max(-0.05, min(0.30, float(g)))

    wacc = cf.wacc(f, beta=beta, rf=rf, erp=erp)
    roce = cf.roce_after_tax(f)
    rr = ratios.all_ratios(f)
    dp = cf.dupont(f)
    val_scen = cf.damodaran_scenarios(f, wacc, base_growth=g)
    implied_g = cf.reverse_dcf_growth(f, wacc)

    # multiples vs secteur (Damodaran : toujours relatif aux comparables)
    mult = {
        "pe": _f(valuation.per(f)), "ev_ebitda": _f(valuation.ev_ebitda(f)),
        "ev_sales": _f(valuation.ev_sales(f)), "price_to_book": _f(valuation.price_to_book(f)),
        "fcf_yield": _f(valuation.fcf_yield(f), 4), "earnings_yield": _f(valuation.earnings_yield(f), 4),
    }
    mult_vs_sector = {k: {"company": mult.get(k), "sector": _f(sm.get(k))}
                      for k in ("pe", "ev_ebitda", "ev_sales", "price_to_book") if sm.get(k)}

    inv = investor_scores(f, f.sector, prior)
    piotroski = scoring.piotroski_full(f, prior) if prior else scoring.f_score(f)
    altman = scoring.altman_z(f)

    # score global /100 : moyenne pondérée de piliers normalisés
    pillars = _pillar_scores(f, rr, roce, wacc, val_scen, piotroski, altman)
    fundamental_score = int(round(sum(p["score"] * p["weight"] for p in pillars.values())))
    tech_score = technical_score(technical)
    ml_sc = int(round(max(0.0, min(1.0, ml_score)) * 100)) if ml_score is not None else None
    # score GLOBAL = fondamental (cœur), ajusté par technique et ML quand disponibles
    parts = [(fundamental_score, 0.6)]
    if tech_score is not None:
        parts.append((tech_score, 0.25))
    if ml_sc is not None:
        parts.append((ml_sc, 0.15))
    wsum = sum(w for _, w in parts)
    global_score = int(round(sum(v * w for v, w in parts) / wsum)) if wsum else fundamental_score
    reco = ("Achat" if global_score >= 65 else "Conserver" if global_score >= 45 else "Vente")

    return {
        "as_of": datetime.now(timezone.utc).date().isoformat(),
        "identity": {"symbol": f.symbol, "name": name or f.symbol, "sector": f.sector,
                     "price": _f(f.price), "market_cap": _f(valuation.market_cap(f), 0),
                     "enterprise_value": _f(valuation.enterprise_value(f), 0), "shares": _f(f.shares, 0)},
        "audit": audit,
        "score": {"global": global_score, "recommendation": reco, "pillars": pillars,
                  "fundamental": fundamental_score, "technical": tech_score, "ml": ml_sc},
        "vernimmen": {
            "roce_after_tax": _f(roce, 4), "wacc": _f(wacc, 4),
            "value_creation_spread": _f((roce - wacc) if roce == roce else None, 4),
            "eva": _f(cf.eva(f, wacc), 0), "capital_employed": _f(cf.capital_employed(f), 0),
            "gearing": _f(cf.gearing(f), 3), "net_debt_ebitda": _f(rr.get("net_debt_ebitda"), 2),
            "interest_coverage": _f(rr.get("interest_coverage"), 1),
            "fcf_conversion": _f(rr.get("fcf_conversion"), 3),
            "dupont": {k: _f(v, 4) for k, v in dp.items()},
            "margins": {"gross": _f(rr.get("gross_margin"), 4), "ebit": _f(rr.get("ebit_margin"), 4),
                        "net": _f(rr.get("net_margin"), 4)},
        },
        "damodaran": {
            "cost_of_equity": _f(cf.cost_of_equity(beta, rf, erp), 4),
            "cost_of_debt": _f(cf.cost_of_debt(f), 4), "wacc": _f(wacc, 4), "beta": _f(beta, 2),
            "dcf": val_scen, "implied_growth_in_price": _f(implied_g, 4),
            "multiples": mult, "multiples_vs_sector": mult_vs_sector,
        },
        "quality": {
            "piotroski_f_score": piotroski, "piotroski_label": scoring.f_score_label(piotroski),
            "altman_z": altman, "investor_scores": inv,
        },
        "technical": technical or None,
        "macro": macro or None,
        "earnings": earnings or None,
        "charts": _charts_block(f, prior, price_series, financial_history),
        "verdict": _verdict(f, global_score, reco, roce, wacc, val_scen, audit),
    }


def _charts_block(f: Financials, prior: Financials | None, price_series: list[float] | None,
                  financial_history: list[dict] | None) -> dict[str, Any]:
    """Données pour les mini-graphes : série de cours (bornée) + historique CA/résultat. À défaut
    d'historique fourni, on dérive 2 points (N-1, N) depuis prior/current — honnête et toujours là."""
    px = [float(x) for x in (price_series or []) if x is not None][-504:]   # ≤ ~2 ans de daily
    hist = financial_history
    if not hist:
        hist = []
        yr = f.as_of.year
        if prior is not None:
            hist.append({"year": yr - 1, "revenue": prior.revenue, "net_income": prior.net_income})
        hist.append({"year": yr, "revenue": f.revenue, "net_income": f.net_income})
    # CAGR du CA sur la période de l'historique (≥3 points = histo réel pluriannuel)
    rev_cagr = None
    rev_pts = [(h.get("year"), h.get("revenue")) for h in hist
               if h.get("revenue") and h.get("revenue") > 0]
    if len(rev_pts) >= 3:
        (y0, v0), (y1, v1) = rev_pts[0], rev_pts[-1]
        n = (y1 - y0) if (y1 and y0 and y1 > y0) else (len(rev_pts) - 1)
        if n > 0 and v0 > 0:
            rev_cagr = round((v1 / v0) ** (1 / n) - 1.0, 4)
    return {"price": px, "financial_history": hist, "revenue_cagr": rev_cagr,
            "history_years": len(hist)}


def _pillar_scores(f: Financials, rr: dict, roce: float, wacc: float, val_scen: dict,
                   piotroski: int, altman: dict) -> dict[str, dict]:
    """Scores 0-100 par pilier + poids (somme = 1). Bornés, robustes aux NaN."""
    def clip(x: float) -> int:
        return int(max(0, min(100, round(x))))

    nm = rr.get("net_margin") or 0.0
    profitability = clip(50 + 250 * nm)                          # 20 % de marge → 100
    spread = (roce - wacc) if roce == roce else 0.0
    value_creation = clip(50 + 500 * spread)                     # +10 pts de spread → 100
    mos = val_scen.get("margin_of_safety")
    valuation_sc = clip(50 + 200 * mos) if mos is not None else 50
    nd = rr.get("net_debt_ebitda")
    solidity = clip(100 - 25 * (nd if (nd is not None and nd == nd) else 1.0)) if (nd is not None) else 60
    solidity = clip(0.6 * solidity + 0.4 * (piotroski / 9 * 100))
    z = altman.get("z")
    safety = clip((z / 6 * 100)) if z is not None else 55
    return {
        "rentabilité": {"score": profitability, "weight": 0.25},
        "création de valeur (ROCE−WACC)": {"score": value_creation, "weight": 0.25},
        "valorisation": {"score": valuation_sc, "weight": 0.20},
        "solidité financière": {"score": solidity, "weight": 0.20},
        "sécurité (Altman)": {"score": safety, "weight": 0.10},
    }


def _verdict(f: Financials, score: int, reco: str, roce: float, wacc: float,
             val_scen: dict, audit: dict) -> dict[str, Any]:
    strengths, watch = [], []
    if roce == roce and roce > wacc:
        strengths.append(f"Crée de la valeur : ROCE {roce*100:.1f}% > WACC {wacc*100:.1f}%.")
    else:
        watch.append("Détruit de la valeur économique (ROCE ≤ WACC).")
    nm = f.net_income / f.revenue if f.revenue else 0
    if nm > 0.15:
        strengths.append(f"Marge nette élevée ({nm*100:.0f}%).")
    mos = val_scen.get("margin_of_safety")
    if mos is not None:
        (strengths if mos > 0 else watch).append(
            f"DCF base : marge de sécurité {mos*100:+.0f}% vs cours.")
    if f.fcf > 0:
        strengths.append("FCF positif.")
    else:
        watch.append("FCF négatif.")
    if not audit["ok"]:
        watch.append("⚠️ Données à fiabilité limitée (voir audit PwC).")
    return {"recommendation": reco, "score": score, "strengths": strengths, "watch": watch}
