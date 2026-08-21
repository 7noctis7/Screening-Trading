"""Pipeline d'alpha fondamental à 4 couches — qualité → valorisation → momentum → taille.

Implémente l'architecture demandée (Graham/Damodaran pour la valeur, CFA pour le timing,
Grinold/Taleb pour la taille) avec **quatre corrections** qu'un desk institutionnel
imposerait, chacune documentée là où elle s'applique :

1. **Classement plutôt que couperets.** Les seuils durs (marge > 20 % ET croissance > 15 %
   ET PER < 25 …) sont conservés — mode `strict` — mais ce n'est PAS le défaut. Une
   conjonction de six couperets sur un univers de 500 titres en laisse passer une poignée,
   parfois zéro : `IR = IC·√BR` s'effondre avec le souffle, et un portefeuille de 3 lignes
   n'a aucune propriété statistique. Le mode `rank` note chaque critère en coupe et garde
   le meilleur quintile : on conserve l'information ET le souffle.
2. **Le DCF est un SCORE, pas une porte.** Sa valeur terminale domine le résultat et dépend
   de (g, WACC) : ±1 point de WACC déplace la juste valeur de 20 à 30 %. Exiger « décote
   ≥ 30 % » sur une estimation aussi sensible, c'est de la précision fictive. On calcule donc
   une **bande de sensibilité** et l'on signale `fragile` quand le SIGNE de la décote
   s'inverse dans la bande — c'est-à-dire quand le DCF ne dit rien.
3. **L'entonnoir est publié.** À chaque couche, combien entrent, combien sortent, et pourquoi.
   C'est le diagnostic qui dit si le screener produit du souffle ou trois lignes.
4. **Le quick ratio n'est pas calculable** depuis `Financials` (ni actif courant ni passif
   courant dans le modèle). Il est donc renvoyé `None` et **exclu** de la conjonction stricte,
   au lieu d'être approximé en silence. Un critère non mesuré ne doit jamais compter comme
   satisfait.

⚠️ **Limite structurelle à connaître avant tout backtest** : les fondamentaux disponibles ici
ne sont PAS point-in-time. Ce pipeline est un **screener LIVE** honnête ; le backtester sur
des états financiers actuels appliqués au passé produirait une courbe magnifique et fausse
(cf. `vault/17_UPGRADE/AXE1_DATA_PIT.md`).

numpy + stdlib.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from packages.fundamentals.models import Financials
from packages.fundamentals.valuation import dcf_intrinsic_per_share, market_cap


@dataclass(frozen=True, slots=True)
class Seuils:
    """Seuils PRÉ-ENREGISTRÉS (mode strict). Ne jamais les ajuster sur les résultats."""
    net_margin_min: float = 0.20
    revenue_growth_min: float = 0.15
    debt_to_equity_max: float = 0.60
    quick_ratio_min: float = 1.0
    ps_max: float = 7.0
    pe_max: float = 25.0
    marge_securite_min: float = 0.30
    quintile: float = 0.20              # mode `rank` : part de l'univers conservée


@dataclass
class Candidat:
    symbole: str
    metriques: dict = field(default_factory=dict)
    valorisation: dict = field(default_factory=dict)
    momentum: dict = field(default_factory=dict)
    taille: dict = field(default_factory=dict)
    score: float = 0.0
    rejets: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------- couche 1
def metriques_qualite(f: Financials) -> dict:
    """Ratios de qualité et de solvabilité. `None` = NON MESURÉ, jamais « satisfait »."""
    mc = market_cap(f)
    def _r(num, den):
        return float(num / den) if den else None
    return {"net_margin": _r(f.net_income, f.revenue),
            "revenue_growth": f.revenue_growth,          # None si la source ne la fournit pas
            "debt_to_equity": _r(f.total_debt, f.total_equity),
            "quick_ratio": None,                          # non calculable (cf. correction 4)
            "price_to_sales": _r(mc, f.revenue),
            "price_to_earnings": _r(mc, f.net_income) if f.net_income > 0 else None,
            "market_cap": mc}


def _viole(m: dict, s: Seuils) -> list[str]:
    """Critères STRICTEMENT violés. Un critère non mesuré n'est ni violé ni satisfait."""
    out = []
    if m["net_margin"] is not None and m["net_margin"] < s.net_margin_min:
        out.append(f"marge {m['net_margin']:.1%} < {s.net_margin_min:.0%}")
    if m["revenue_growth"] is not None and m["revenue_growth"] < s.revenue_growth_min:
        out.append(f"croissance {m['revenue_growth']:.1%} < {s.revenue_growth_min:.0%}")
    if m["debt_to_equity"] is not None and m["debt_to_equity"] > s.debt_to_equity_max:
        out.append(f"D/E {m['debt_to_equity']:.2f} > {s.debt_to_equity_max}")
    if m["price_to_sales"] is not None and m["price_to_sales"] > s.ps_max:
        out.append(f"P/S {m['price_to_sales']:.1f} > {s.ps_max}")
    if m["price_to_earnings"] is None:
        out.append("PER non calculable (bénéfice ≤ 0)")
    elif m["price_to_earnings"] > s.pe_max:
        out.append(f"PER {m['price_to_earnings']:.1f} > {s.pe_max}")
    return out


# --------------------------------------------------------------------------- couche 2
def valorisation_dcf(f: Financials, wacc: float = 0.09, growth: float = 0.06,
                     terminal_growth: float = 0.02) -> dict:
    """Juste valeur DCF + BANDE DE SENSIBILITÉ (WACC ±1 pt, croissance ±2 pts).

    `fragile=True` quand le signe de la marge de sécurité s'inverse dans la bande : le DCF
    ne tranche alors rien, et prétendre le contraire est une erreur de méthode.
    """
    base = dcf_intrinsic_per_share(f, wacc=wacc, growth=growth,
                                   terminal_growth=terminal_growth)
    if not (base == base) or f.price <= 0:
        return {"available": False, "raison": "FCF ≤ 0 ou données manquantes"}
    mos = []
    for dw in (-0.01, 0.0, 0.01):
        for dg in (-0.02, 0.0, 0.02):
            v = dcf_intrinsic_per_share(f, wacc=wacc + dw, growth=max(0.0, growth + dg),
                                        terminal_growth=terminal_growth)
            if v == v:
                mos.append(v / f.price - 1.0)
    if not mos:
        return {"available": False, "raison": "DCF non calculable sur la bande"}
    lo, hi = float(min(mos)), float(max(mos))
    return {"available": True, "juste_valeur": round(float(base), 2),
            "marge_securite": round(float(base / f.price - 1.0), 4),
            "bande_basse": round(lo, 4), "bande_haute": round(hi, 4),
            "fragile": bool(lo < 0 < hi),
            "note": ("le signe de la décote s'inverse dans la bande de sensibilité : "
                     "le DCF ne conclut pas" if lo < 0 < hi else "")}


# --------------------------------------------------------------------------- couche 3
def _ema(x: np.ndarray, span: int) -> float:
    a = 2.0 / (span + 1.0)
    out = float(x[0])
    for v in x[1:]:
        out = a * float(v) + (1 - a) * out
    return out


def signal_momentum(closes, volumes=None) -> dict:
    """Timing : cours > EMA50, EMA50 > EMA200, et volume du jour > moyenne 20 séances."""
    c = np.asarray(closes, dtype=float)
    c = c[np.isfinite(c)]
    if c.size < 200:
        return {"available": False, "raison": f"{c.size} séances < 200"}
    e50, e200 = _ema(c[-250:], 50), _ema(c, 200)
    vol_ok = None
    if volumes is not None:
        v = np.asarray(volumes, dtype=float)
        v = v[np.isfinite(v)]
        if v.size >= 21:
            vol_ok = bool(v[-1] > v[-21:-1].mean())
    au_dessus, tendance = bool(c[-1] > e50), bool(e50 > e200)
    return {"available": True, "prix": float(c[-1]), "ema50": round(e50, 4),
            "ema200": round(e200, 4), "au_dessus_ema50": au_dessus,
            "tendance_haussiere": tendance, "volume_confirme": vol_ok,
            "valide": bool(au_dessus and tendance and (vol_ok is not False))}


# --------------------------------------------------------------------------- couche 4
def expected_shortfall(returns, alpha: float = 0.95) -> float:
    """ES historique (perte moyenne dans les pires 1−alpha) — jamais de VaR gaussienne."""
    from packages.portfolio.risk_metrics import cvar_historical
    return float(cvar_historical(returns, alpha=alpha))


def taille_position(returns, roundtrips=None, es_budget: float = 0.01,
                    cap: float = 0.05, dd_limit: float = 0.25,
                    dd_prob: float = 0.05) -> dict:
    """Kelly fractionnaire PONDÉRÉ PAR L'ES, plafonné à `cap` du capital.

    Deux briques superposées, dans cet ordre :
      1. budget d'ES : `w = es_budget / ES_95(actif)` — chaque ligne contribue au MÊME
         risque de queue, ce qui neutralise l'écart de volatilité entre un indice (15 %)
         et une crypto (70 %) ;
      2. fraction de Kelly **dérivée d'un budget de drawdown** (et non posée à 0,25) sur les
         round-trips RÉELS s'il y en a assez ; sinon la couche 1 seule décide.
    """
    es = expected_shortfall(returns)
    if es <= 0:
        return {"available": False, "raison": "ES nul ou négatif"}
    w_es = es_budget / es
    lam = None
    if roundtrips is not None:
        from packages.portfolio.sizing.kelly_fat_tail import sized_fraction
        k = sized_fraction(roundtrips, dd_limit=dd_limit, dd_prob=dd_prob, cap=1.0)
        if k.get("available"):
            lam = float(k["fraction"])
    w = min(w_es if lam is None else w_es * lam, cap)
    return {"available": True, "es_95": round(es, 5), "poids_par_budget_es": round(w_es, 4),
            "fraction_kelly": lam, "poids": round(float(max(0.0, w)), 4), "cap": cap,
            "statut": "UNCALIBRATED (Kelly)" if lam is None else "calibré"}


def stop_atr(highs, lows, closes, window: int = 14, mult: float = 2.0) -> dict:
    """Trailing stop à `mult` × ATR(14) — s'adapte à la volatilité réelle de l'actif."""
    h, l, c = (np.asarray(x, dtype=float) for x in (highs, lows, closes))
    n = min(h.size, l.size, c.size)
    if n < window + 1:
        return {"available": False}
    h, l, c = h[-n:], l[-n:], c[-n:]
    tr = np.maximum(h[1:] - l[1:], np.maximum(np.abs(h[1:] - c[:-1]), np.abs(l[1:] - c[:-1])))
    a = float(tr[-window:].mean())
    return {"available": True, "atr": round(a, 4), "mult": mult,
            "stop_long": round(float(c[-1] - mult * a), 4),
            "distance_pct": round(float(mult * a / c[-1]), 4)}


# --------------------------------------------------------------------- orchestration
def _z(vals: list[float | None]) -> np.ndarray:
    """z robuste (médiane/MAD) en coupe ; les non-mesurés reçoivent 0 = neutre."""
    from packages.ranking.orthogonalize import robust_z
    arr = np.array([v if v is not None else np.nan for v in vals], dtype=float)
    return robust_z(arr)


def run_pipeline(financials: list[Financials], prices: dict[str, dict],
                 mode: str = "rank", seuils: Seuils | None = None,
                 es_budget: float = 0.01, cap: float = 0.05) -> dict:
    """Exécute les 4 couches et publie l'ENTONNOIR.

    `mode="rank"` (défaut) : classement en coupe, meilleur quintile conservé — préserve le
    souffle. `mode="strict"` : couperets du cahier des charges — à comparer, car c'est
    l'entonnoir qui montre si la conjonction laisse passer un portefeuille ou trois lignes.
    """
    if mode not in ("rank", "strict"):
        raise ValueError("mode ∈ {'rank', 'strict'}")
    s = seuils or Seuils()
    entonnoir = [{"couche": "univers", "entrent": len(financials), "sortent": len(financials)}]
    cands = {f.symbol: Candidat(f.symbol, metriques=metriques_qualite(f)) for f in financials}

    # ---- couche 1 : qualité & solvabilité
    if mode == "strict":
        for f in financials:
            v = _viole(cands[f.symbol].metriques, s)
            cands[f.symbol].rejets += v
        garde1 = [f.symbol for f in financials if not cands[f.symbol].rejets]
    else:
        syms = [f.symbol for f in financials]
        M = [cands[x].metriques for x in syms]
        comp = (_z([m["net_margin"] for m in M]) + _z([m["revenue_growth"] for m in M])
                - _z([m["debt_to_equity"] for m in M]) - _z([m["price_to_sales"] for m in M])
                - _z([m["price_to_earnings"] for m in M]))
        k = max(1, int(round(len(syms) * s.quintile)))
        ordre = np.argsort(comp)[::-1][:k]
        garde1 = [syms[i] for i in ordre]
        for i, x in enumerate(syms):
            cands[x].score = float(comp[i])
    entonnoir.append({"couche": "1 · qualité", "entrent": len(financials),
                      "sortent": len(garde1)})

    # ---- couche 2 : valorisation & marge de sécurité
    garde2 = []
    fragiles = 0
    for f in financials:
        if f.symbol not in garde1:
            continue
        v = valorisation_dcf(f)
        cands[f.symbol].valorisation = v
        if not v.get("available"):
            cands[f.symbol].rejets.append(f"DCF indisponible : {v.get('raison')}")
            continue
        if v["fragile"]:
            fragiles += 1
            cands[f.symbol].rejets.append("DCF fragile (le signe de la décote s'inverse)")
            continue
        if mode == "strict" and v["marge_securite"] < s.marge_securite_min:
            cands[f.symbol].rejets.append(
                f"décote {v['marge_securite']:.1%} < {s.marge_securite_min:.0%}")
            continue
        garde2.append(f.symbol)
    if mode == "rank" and garde2:
        garde2.sort(key=lambda x: -cands[x].valorisation["marge_securite"])
        garde2 = garde2[:max(1, int(round(len(garde2) * 0.5)))]     # moitié la moins chère
    entonnoir.append({"couche": "2 · valorisation", "entrent": len(garde1),
                      "sortent": len(garde2), "dont_dcf_fragile": fragiles})

    # ---- couche 3 : momentum (identique dans les deux modes)
    garde3 = []
    for x in garde2:
        px = prices.get(x) or {}
        m = signal_momentum(px.get("closes", []), px.get("volumes"))
        cands[x].momentum = m
        if m.get("available") and m["valide"]:
            garde3.append(x)
        else:
            cands[x].rejets.append("momentum non validé" if m.get("available")
                                   else f"momentum : {m.get('raison')}")
    entonnoir.append({"couche": "3 · momentum", "entrent": len(garde2),
                      "sortent": len(garde3)})

    # ---- couche 4 : dimensionnement
    retenus = []
    for x in garde3:
        px = prices.get(x) or {}
        t = taille_position(px.get("returns", []), roundtrips=px.get("roundtrips"),
                            es_budget=es_budget, cap=cap)
        cands[x].taille = t
        if t.get("available") and t["poids"] > 0:
            if all(k in px for k in ("highs", "lows", "closes")):
                cands[x].taille["stop"] = stop_atr(px["highs"], px["lows"], px["closes"])
            retenus.append(x)
        else:
            cands[x].rejets.append(f"taille : {t.get('raison', 'poids nul')}")
    entonnoir.append({"couche": "4 · dimensionnement", "entrent": len(garde3),
                      "sortent": len(retenus)})

    brut = sum(cands[x].taille.get("poids", 0.0) for x in retenus)
    return {"mode": mode, "entonnoir": entonnoir,
            "candidats": [cands[x] for x in retenus],
            "rejetes": {x: cands[x].rejets for x in cands if x not in retenus},
            "gross_expose": round(brut, 4),
            "souffle_suffisant": len(retenus) >= 10,
            "avertissement": ("fondamentaux NON point-in-time : screener LIVE uniquement, "
                              "tout backtest sur ces données serait faux")}
