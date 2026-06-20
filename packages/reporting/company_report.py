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
# métriques de positionnement : (clé, libellé, plus_haut_est_mieux)
_PEER_METRICS = [
    ("net_margin", "Marge nette", True), ("roe", "ROE", True), ("roic", "ROIC", True),
    ("gross_margin", "Marge brute", True), ("per", "P/E", False), ("ev_ebitda", "EV/EBITDA", False),
    ("revenue_growth", "Croissance CA", True),
]


def _median(xs: list[float]) -> float | None:
    xs = sorted(v for v in xs if v is not None and v == v)
    if not xs:
        return None
    n = len(xs)
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2


def sector_positioning(company: dict[str, Any], peers: list[dict[str, Any]]) -> dict[str, Any]:
    """Positionne la société vs ses pairs SECTORIELS : médiane, percentile et verdict (favorable/
    défavorable) par métrique, direction-aware (P/E bas = favorable, marge haute = favorable).
    `peers` : métriques des sociétés du même secteur (incluant ou non la société). Pur, robuste."""
    rows = []
    for key, label, higher in _PEER_METRICS:
        cval = company.get(key)
        vals = [p.get(key) for p in peers if p.get(key) is not None and p.get(key) == p.get(key)]
        med = _median(vals)
        if cval is None or cval != cval or med is None or len(vals) < 3:
            continue
        below = sum(1 for v in vals if v < cval)
        pct = below / len(vals)                              # rang percentile brut (part sous la société)
        rank = pct if higher else (1 - pct)                 # normalisé : 1 = meilleur du secteur
        verdict = "favorable" if ((cval >= med) == higher) else "défavorable"
        rows.append({"metric": key, "label": label, "company": round(float(cval), 4),
                     "sector_median": round(float(med), 4), "percentile": round(rank, 2),
                     "verdict": verdict})
    fav = sum(1 for r in rows if r["verdict"] == "favorable")
    return {"available": bool(rows), "n_peers": len(peers), "rows": rows,
            "favorable": fav, "total": len(rows)}


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
                         price_dates: list[str] | None = None,
                         financial_history: list[dict] | None = None,
                         peers: list[dict[str, Any]] | None = None) -> dict[str, Any]:
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

    # GATE DE PLAUSIBILITÉ DE LA VALORISATION (PwC) : pour les ADR (TSM, ASML.AS…), la source publie
    # souvent les comptes en DEVISE LOCALE alors que le cours est en USD → multiples & DCF absurdes
    # (P/E ≪ 1, EV/EBITDA ≈ 0, DCF ≫ cours). On DÉTECTE l'incohérence, on MASQUE les chiffres
    # trompeurs et on le signale, au lieu d'afficher une valorisation fausse.
    val_reliable, val_reasons = _valuation_plausible(f, mult, val_scen)
    if not val_reliable:
        val_scen = {**val_scen, "reliable": False, "margin_of_safety": None}
        for r in val_reasons:
            audit["findings"].append({"severity": "warning", "detail": r})
        audit["counts"]["warning"] = audit["counts"].get("warning", 0) + len(val_reasons)
    else:
        val_scen["reliable"] = True

    inv = investor_scores(f, f.sector, prior)
    piotroski = scoring.piotroski_full(f, prior) if prior else scoring.f_score(f)
    altman = scoring.altman_z(f)

    # positionnement sectoriel (vs pairs) — direction-aware, percentile + verdict.
    # Métriques ASSAINIES : on écarte les valeurs implausibles (devise mixte) pour ne pas polluer.
    def _san(v, lo, hi):
        return v if (v is not None and v == v and lo <= v <= hi) else None
    company_metrics = {"net_margin": _san(rr.get("net_margin"), -2, 1), "roe": _san(rr.get("roe"), -5, 5),
                       "roic": _san(rr.get("roic"), -1, 3), "gross_margin": _san(rr.get("gross_margin"), -0.1, 1),
                       "per": (mult.get("pe") if val_reliable else None),
                       "ev_ebitda": (mult.get("ev_ebitda") if val_reliable else None),
                       "revenue_growth": _san(f.revenue_growth, -1, 10)}
    sector_comparison = sector_positioning(company_metrics, peers) if peers else {"available": False}

    # RISQUE DE PRIX (Citadel/JPM) : marge de sécurité DCF Base. Un actif d'exception payé à un prix
    # absurde reste un mauvais investissement → pilier Valorisation à 0 et pénalité globale ≤ 40 %.
    mos = val_scen.get("margin_of_safety")
    overvalued = bool(val_reliable and mos is not None and mos < -0.30)

    # score global /100 : moyenne pondérée de piliers normalisés
    pillars = _pillar_scores(f, rr, roce, wacc, val_scen, piotroski, altman, val_reliable, overvalued)
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
    # pénalité de surévaluation : nulle à −30 %, maximale (−40 %) à partir de −70 %
    penalty = 1.0
    if overvalued:
        sev = min(1.0, (abs(mos) - 0.30) / 0.40)
        penalty = 1.0 - 0.40 * sev
        global_score = int(round(global_score * penalty))
    reco = ("Achat" if global_score >= 65 else "Neutre" if global_score >= 45 else "Sous surveillance")
    verdict_status = reco.upper()

    charts = _charts_block(f, prior, price_series, financial_history, price_dates)
    snow = snowflake(valuation_score=pillars["valorisation"]["score"], revenue_growth=f.revenue_growth,
                     ml_score=ml_score, revenue_cagr=charts.get("revenue_cagr"),
                     roe=dp.get("roe"), piotroski=piotroski, altman_z=altman.get("z"))

    return {
        "as_of": datetime.now(timezone.utc).date().isoformat(),
        "identity": {"symbol": f.symbol, "name": name or f.symbol, "sector": f.sector,
                     "price": _f(f.price), "market_cap": _f(valuation.market_cap(f), 0),
                     "enterprise_value": _f(valuation.enterprise_value(f), 0), "shares": _f(f.shares, 0)},
        "audit": audit,
        "score": {"global": global_score, "recommendation": reco, "verdict_status": verdict_status,
                  "pillars": pillars, "fundamental": fundamental_score, "technical": tech_score,
                  "ml": ml_sc, "valuation_penalty": round(penalty, 2)},
        "flags": {"overvalued": overvalued, "blocking_alert": False},
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
        "memo": _memo(f, name or f.symbol, global_score, reco, roce, wacc, val_scen,
                      rr, sector_comparison),
        "memo_source": "synthèse (règles)",
        "sector_comparison": sector_comparison,
        "technical": technical or None,
        "macro": macro or None,
        "earnings": earnings or None,
        "charts": charts,
        "snowflake": snow,
        "risk": risk_block(price_series, beta),
        "verdict": _verdict(f, global_score, reco, roce, wacc, val_scen, audit),
    }


def snowflake(*, valuation_score: int, revenue_growth: float | None, ml_score: float | None,
              revenue_cagr: float | None, roe: float | None, piotroski: int, altman_z: float | None,
              dividend_yield: float | None = None) -> dict[str, Any]:
    """Radar « Portfolio Snowflake » (style Simply Wall St) — 5 axes 0-100, cohérents avec les
    fondamentaux : VALUE (valorisation), FUTURE (croissance attendue), PAST (performance passée),
    HEALTH (solidité financière), DIVIDEND (rendement). Pur, robuste aux None."""
    def clip(x: float) -> int:
        return int(max(0, min(100, round(x))))

    value = clip(valuation_score)                                  # déjà 0-100 (gate incluse)
    rg = revenue_growth if revenue_growth is not None else 0.0
    mlc = (ml_score * 100 if ml_score is not None else 50)
    future = clip(45 + 180 * max(-0.2, min(0.4, rg)) + (mlc - 50) * 0.35)
    cagr = revenue_cagr if revenue_cagr is not None else 0.0
    roe_v = roe if roe is not None else 0.0
    past = clip(35 + 180 * max(-0.2, min(0.5, cagr)) + 60 * max(-0.2, min(0.6, roe_v)))
    z = altman_z if altman_z is not None else 3.0
    health = clip(0.5 * (piotroski / 9 * 100) + 0.5 * max(0, min(100, z / 6 * 100)))
    dividend = clip((dividend_yield or 0.0) * 100 * 12)           # ~8 %+ → plein ; 0 = non-payeur
    axes = {"VALUE": value, "FUTURE": future, "PAST": past, "HEALTH": health, "DIVIDEND": dividend}
    # résumé en langage naturel (axes saillants)
    tags = []
    if past >= 60:
        tags.append("past performer" if future < 60 else "established performer")
    if future >= 60:
        tags.append("good growth potential")
    if value >= 60:
        tags.append("trading below fair value")
    elif value <= 25:
        tags.append("expensive vs fair value")
    if health >= 70:
        tags.append("solid balance sheet")
    if dividend >= 50:
        tags.append("dividend payer")
    summary = (", ".join(tags[:3]).capitalize() + ".") if tags else "Profil équilibré."
    return {"axes": axes, "summary": summary,
            "dividend_known": dividend_yield is not None}


def risk_block(closes: list[float] | None, beta: float | None = None) -> dict[str, Any]:
    """Risk management de l'actif depuis les cours réels : vol annualisée, max drawdown, VaR/CVaR 95 %
    (historique 1 j), Sharpe & Sortino (rf=0), bêta, stop suggéré (~2σ hebdo). Pur, ne lève jamais."""
    import math
    px = [float(x) for x in (closes or []) if x is not None]
    if len(px) < 30:
        return {"available": False}
    rets = [px[i] / px[i - 1] - 1.0 for i in range(1, len(px)) if px[i - 1]]
    n = len(rets)
    mu = sum(rets) / n
    sd = (sum((x - mu) ** 2 for x in rets) / (n - 1)) ** 0.5 if n > 1 else 0.0
    dn = [min(0.0, x) for x in rets]
    dsd = (sum(x * x for x in dn) / n) ** 0.5
    vol_a = sd * math.sqrt(252)
    sharpe = (mu / sd * math.sqrt(252)) if sd > 0 else 0.0
    sortino = (mu / dsd * math.sqrt(252)) if dsd > 0 else 0.0
    # max drawdown
    peak, mdd = px[0], 0.0
    for v in px:
        peak = max(peak, v); mdd = min(mdd, v / peak - 1.0)
    # VaR / CVaR 95 % historiques (perte 1 j)
    s = sorted(rets)
    k = max(0, int(0.05 * len(s)) - 1)
    var95 = -s[k]
    tail = s[: k + 1]
    cvar95 = -(sum(tail) / len(tail)) if tail else var95
    stop = -2.0 * sd * math.sqrt(5)               # ~2σ sur 5 séances (stop hebdo indicatif)
    return {"available": True, "vol_annual": round(vol_a, 4), "max_drawdown": round(mdd, 4),
            "var_95": round(var95, 4), "cvar_95": round(cvar95, 4), "sharpe": round(sharpe, 2),
            "sortino": round(sortino, 2), "beta": (round(float(beta), 2) if beta is not None else None),
            "suggested_stop": round(stop, 4)}


def _charts_block(f: Financials, prior: Financials | None, price_series: list[float] | None,
                  financial_history: list[dict] | None, price_dates: list[str] | None = None) -> dict[str, Any]:
    """Données pour les mini-graphes : série de cours (bornée) + dates (axe X) + historique CA/résultat.
    À défaut d'historique fourni, on dérive 2 points (N-1, N) depuis prior/current — honnête."""
    series = [(d, float(x)) for d, x in zip(price_dates or [None] * len(price_series or []),
                                            (price_series or [])) if x is not None][-504:]  # ≤ ~2 ans
    px = [v for _, v in series]
    px_labels = [str(d)[:10] for d, _ in series if d]
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
    return {"price": px, "price_labels": px_labels, "financial_history": hist,
            "revenue_cagr": rev_cagr, "history_years": len(hist)}


def _valuation_plausible(f: Financials, mult: dict, val_scen: dict) -> tuple[bool, list[str]]:
    """Garde-fou PwC : détecte une valorisation INCOHÉRENTE (typiquement ADR dont les comptes sont en
    devise locale alors que le cours est en USD → P/E ≪ 1, EV/EBITDA ≈ 0, DCF ≫ cours). Renvoie
    (fiable, raisons). Les ratios purement comptables (marges, ROCE) restent valides."""
    # On ne flague QUE la signature « comptes en plus grosse devise » : grandeurs comptables TROP
    # GRANDES vs le cours → P/E ≪ 1, EV/EBITDA ≈ 0, P/S extrême, DCF ≫ cours. Un P/E ÉLEVÉ (société
    # à faibles marges / turnaround) est légitime et ne doit PAS être confondu avec une devise mixte.
    reasons: list[str] = []
    mcap = f.price * f.shares
    pe = mult.get("pe")
    ev_eb = mult.get("ev_ebitda")
    ps = (mcap / f.revenue) if f.revenue > 0 else None
    base = (val_scen.get("scenarios") or {}).get("base")
    if pe is not None and 0 < pe < 2:
        reasons.append(f"P/E implausible ({pe}) — devise des comptes ≠ devise du cours (ADR ?)")
    if ev_eb is not None and 0 < ev_eb < 1:
        reasons.append(f"EV/EBITDA implausible ({ev_eb}) — incohérence d'unités/devise")
    if ps is not None and (ps < 0.03 or ps > 100):
        reasons.append(f"P/S implausible ({ps:.2f}) — incohérence d'unités/devise")
    if base and f.price and (base / f.price) > 10:
        reasons.append(f"DCF ({base:.0f}) ≫ cours ({f.price:.0f}) — valorisation peu fiable")
    return (len(reasons) == 0), reasons


def _pillar_scores(f: Financials, rr: dict, roce: float, wacc: float, val_scen: dict,
                   piotroski: int, altman: dict, val_reliable: bool = True,
                   overvalued: bool = False) -> dict[str, dict]:
    """Scores 0-100 par pilier + poids (somme = 1). Bornés, robustes aux NaN."""
    def clip(x: float) -> int:
        return int(max(0, min(100, round(x))))

    nm = rr.get("net_margin") or 0.0
    profitability = clip(50 + 250 * max(-0.4, min(0.4, nm)))      # borné (anti devise mixte)
    spread = (roce - wacc) if roce == roce else 0.0
    value_creation = clip(50 + 500 * max(-0.1, min(0.1, spread))) # +10 pts de spread → 100
    mos = val_scen.get("margin_of_safety")
    if overvalued:                                               # surévaluation sévère (< −30 %) → 0
        valuation_sc = 0
    elif mos is not None and val_reliable:
        valuation_sc = clip(50 + 200 * mos)
    else:
        valuation_sc = 50                                       # neutre si non fiable
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


def _memo(f: Financials, name: str, score: int, reco: str, roce: float, wacc: float,
          val_scen: dict, rr: dict, sector_cmp: dict) -> str:
    """Mémo de synthèse déterministe (2-3 phrases, fort impact) — toujours présent, sans LLM."""
    nm = rr.get("net_margin")
    mos = val_scen.get("margin_of_safety")
    creates = (roce == roce and roce > wacc)
    parts = [f"{name} obtient {score}/100 — recommandation {reco.lower()}."]
    if creates:
        parts.append(f"L'entreprise crée de la valeur (ROCE {roce*100:.0f}% > WACC {wacc*100:.0f}%)"
                     + (f", avec une marge nette de {nm*100:.0f}%." if nm else "."))
    else:
        parts.append("La rentabilité économique ne couvre pas le coût du capital (ROCE ≤ WACC).")
    if mos is not None:
        parts.append(f"Le DCF base ressort {'sous-évalué' if mos>0 else 'au-dessus du cours'} "
                     f"({mos*100:+.0f}% de marge de sécurité).")
    if sector_cmp.get("available"):
        parts.append(f"Vs son secteur : {sector_cmp.get('favorable',0)}/{sector_cmp.get('total',0)} "
                     f"métriques favorables.")
    return " ".join(parts)


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
