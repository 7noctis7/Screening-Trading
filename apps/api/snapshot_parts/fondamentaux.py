"""Fondamentaux : fournisseurs, chaîne de repli, investisseurs.

Extrait TEL QUEL de `apps/api/snapshot.py` le 31/10 (règle des 400 lignes par fichier) : le
texte des définitions n'a pas changé. `apps/api/snapshot.py` reste la façade et ré-exporte
chaque nom, donc `from apps.api.snapshot import X` fonctionne comme avant.
"""

from __future__ import annotations

SANS_SOURCE_REELLE = ("indisponible : aucune source fondamentale réelle n'a répondu "
                      "(le repli synthétique est retiré : un chiffre inventé "
                      "n'est pas noté)")


def _fund_provider():
    """Provider fondamentaux. Priorité : FMP (clé) → **yfinance par défaut si en ligne** → synthétique.

    - **FMP** : réel, free tier limité (~40 actifs) — si `FMP_API_KEY`.
    - **yfinance** : réel, GRATUIT sans clé — utilisé **par défaut** quand le réseau répond
      (désactivable avec `QUANT_FUND=synthetic` pour forcer l'offline/démo).
    - **synthétique** : fondamentaux FABRIQUÉS (déterministes) → repli hors-ligne, PAS pour décider.
    """
    import os
    mode = os.environ.get("QUANT_FUND", "").lower()
    if os.environ.get("FMP_API_KEY") and mode != "synthetic":
        try:
            from packages.fundamentals.fmp_provider import FMPFundamentalsProvider
            return FMPFundamentalsProvider(), "FMP (free tier)"
        except Exception:  # noqa: BLE001
            pass
    # yfinance par défaut (réel, gratuit) sauf demande explicite de synthétique ; garde-fou réseau.
    if mode != "synthetic":
        try:
            from packages.common.net import online
            if mode == "yf" or online():
                from packages.fundamentals.yfinance_provider import (
                    YFinanceFundamentalsProvider,
                )
                return YFinanceFundamentalsProvider(), "yfinance (réel, gratuit)"
        except Exception:  # noqa: BLE001
            pass
    # PLUS DE REPLI SYNTHÉTIQUE IMPLICITE (06/10) : un fondamental inventé ne devient
    # pas un score affiché. Le synthétique reste une DÉMO demandée explicitement.
    if mode == "synthetic":
        from packages.fundamentals.provider import SyntheticFundamentalsProvider
        return (SyntheticFundamentalsProvider(),
                "synthétique (démo : QUANT_FUND=synthetic)")
    return None, SANS_SOURCE_REELLE


def _fund_provider_chain() -> list:
    """Chaîne ORDONNÉE de providers fondamentaux pour 1 actif : yfinance → FMP (si clé) → SEC EDGAR,
    avec le synthétique en DERNIER recours (offline) → une note est TOUJOURS produite."""
    import os as _osf
    mode = _osf.environ.get("QUANT_FUND", "").lower()
    out: list = []
    if mode != "synthetic":
        try:
            from packages.common.net import online
            net = (mode == "yf") or online()
        except Exception:  # noqa: BLE001
            net = False
        if net:
            try:
                from packages.fundamentals.yfinance_provider import (
                    YFinanceFundamentalsProvider,
                )
                out.append(("yfinance (réel)", YFinanceFundamentalsProvider()))
            except Exception:  # noqa: BLE001
                pass
        if _osf.environ.get("FMP_API_KEY"):
            try:
                from packages.fundamentals.fmp_provider import FMPFundamentalsProvider
                out.append(("FMP (réel)", FMPFundamentalsProvider()))
            except Exception:  # noqa: BLE001
                pass
        if net:
            try:
                from packages.fundamentals.sec_provider import SECFundamentalsProvider
                out.append(("SEC EDGAR (réel)", SECFundamentalsProvider()))
            except Exception:  # noqa: BLE001
                pass
    if mode == "synthetic":                      # démo explicite seulement (06/10)
        from packages.fundamentals.provider import SyntheticFundamentalsProvider
        out.append(("synthétique (démo)", SyntheticFundamentalsProvider()))
    return out


def fetch_financials_chain(symbol: str):
    """Récupère un `Financials` pour UN symbole via la chaîne réelle (yfinance→FMP→SEC EDGAR) puis
    le synthétique en repli, + l'exercice N-1 si la source l'expose. Renvoie (financials, prior,
    source). Sert la note d'analyse (endpoint /api/company_report) — produit TOUJOURS une note."""
    for src, prov in _fund_provider_chain():
        try:
            f = prov.get(symbol)
        except Exception:  # noqa: BLE001
            f = None
        if f is None:
            continue
        prior = None
        for meth in ("get_prior", "get_previous"):
            fn = getattr(prov, meth, None)
            if callable(fn):
                try:
                    prior = fn(symbol)
                except Exception:  # noqa: BLE001
                    prior = None
                break
        return f, prior, src
    return None, None, "indisponible"


def _fundamentals_section(symbols: list, acmap: dict, names: dict, sector_of: dict,
                          data: dict | None = None) -> dict:
    """Analyse FONDAMENTALE : ratios (PER, EV/EBITDA, P/B, ROE/ROIC, marges), valorisation DCF
    (marge de sécurité) et score composite value+quality. Equities/ETF uniquement.
    Sources réelles seulement ; sans source, la section est indisponible (06/10)."""
    import os as _osf

    from packages.fundamentals import ratios, valuation
    from packages.fundamentals.scoring import altman_z, f_score, f_score_label

    all_eq = [s for s in symbols if acmap.get(s) in ("equity", "etf")]
    if not all_eq:
        return {"available": False}
    # SOURCES RÉELLES EN CHAÎNE, PAR ACTIF : yfinance → FMP (clé) → SEC EDGAR. On couvre TOUT
    # l'univers actions (pas de plafond), en parallèle ; le synthétique n'est qu'un repli hors-ligne.
    _mode = _osf.environ.get("QUANT_FUND", "").lower()
    _providers: list = []
    if _mode != "synthetic":
        try:
            from packages.common.net import online
            _net = (_mode == "yf") or online()
        except Exception:  # noqa: BLE001
            _net = False
        if _net:
            try:
                from packages.fundamentals.yfinance_provider import (
                    YFinanceFundamentalsProvider,
                )
                _providers.append(("yfinance", YFinanceFundamentalsProvider()))
            except Exception:  # noqa: BLE001
                pass
        if _osf.environ.get("FMP_API_KEY"):
            try:
                from packages.fundamentals.fmp_provider import FMPFundamentalsProvider
                _providers.append(("FMP", FMPFundamentalsProvider()))
            except Exception:  # noqa: BLE001
                pass
        if _net:
            try:
                from packages.fundamentals.sec_provider import SECFundamentalsProvider
                _providers.append(("SEC", SECFundamentalsProvider()))
            except Exception:  # noqa: BLE001
                pass
    cap = int(_osf.environ.get("QUANT_FUND_MAX", "1200"))   # large → couvre tout l'univers actions
    eq = all_eq[:cap]
    capped = len(all_eq) > cap
    by_source: dict[str, int] = {}

    def _chain_fetch(universe: list) -> dict:
        """1re source RÉELLE qui répond pour chaque actif (yfinance → FMP → SEC), en parallèle."""
        from concurrent.futures import ThreadPoolExecutor

        def _one(s):
            for label, p in _providers:
                try:
                    f = p.get(s)
                except Exception:  # noqa: BLE001
                    f = None
                if f is not None:
                    return s, label, f
            return s, None, None
        out: dict = {}
        # défaut PRUDENT (6) : trop de threads yfinance simultanés saturent la RAM (Killed:9 / OOM).
        # Montable via QUANT_FUND_WORKERS si la machine a de la marge.
        workers = max(2, min(16, int(_osf.environ.get("QUANT_FUND_WORKERS", "6"))))
        with ThreadPoolExecutor(max_workers=workers) as ex:
            for s, label, f in ex.map(_one, universe):
                if f is not None:
                    out[s] = f
                    by_source[label] = by_source.get(label, 0) + 1
        return out

    def _rows_for(fin_by: dict, universe: list):
        out = []
        for s in universe:
            f = fin_by.get(s)
            if f is None:
                continue
            mos = valuation.margin_of_safety(f)
            fs = f_score(f)                            # solidité 0-9 RÉELLE (signaux de l'exercice courant)
            mcap = valuation.market_cap(f)
            ps = mcap / f.revenue if f.revenue else None          # price-to-sales
            # NB : les croissances YoY (CA/bénéf.) sont volontairement RETIRÉES — trop volatiles/aberrantes
            # sur les small-caps (dénominateur ≈ 0) → hors tableau et hors notation.
            _az = altman_z(f)
            out.append({
                "symbol": s, "name": names.get(s, ""), "sector": sector_of.get(s, ""),
                "per": round(valuation.per(f), 1), "ev_ebitda": round(valuation.ev_ebitda(f), 1),
                "pb": round(valuation.price_to_book(f), 2),
                "ps": None if ps is None else round(ps, 2),
                "roe": round(ratios.roe(f), 3),
                "roic": round(ratios.roic(f), 3), "gross_margin": round(ratios.gross_margin(f), 3),
                "net_margin": round(ratios.net_margin(f), 3),
                "fcf_yield": round(valuation.fcf_yield(f), 3),
                "margin_of_safety": None if mos != mos else round(mos, 3),
                "f_score": fs, "f_score_label": f_score_label(fs),
                "altman_z": _az["z"], "altman_zone": _az["zone"],
                "per_raw": valuation.per(f),
                "_val": (valuation.earnings_yield(f) + valuation.fcf_yield(f)),
                "_qual": (ratios.roic(f) + ratios.gross_margin(f) + ratios.fcf_conversion(f)),
            })
        return out

    rows = []
    if _providers:
        rows = _rows_for(_chain_fetch(eq), eq)
        src = "réel multi-source : " + " → ".join(
            f"{k} {v}" for k, v in sorted(by_source.items(), key=lambda kv: -kv[1])) if by_source else "réel"
    if not rows and _mode == "synthetic":            # démo explicite seulement (06/10)
        from packages.fundamentals.provider import SyntheticFundamentalsProvider
        sp = SyntheticFundamentalsProvider()
        eq, capped = all_eq, False
        rows = _rows_for({s: sp.get(s) for s in eq}, eq)
        src = "synthétique (démo : QUANT_FUND=synthetic)"
    if not rows:
        return {"available": False, "reason": SANS_SOURCE_REELLE}

    # score composite 0-100 = rang percentile (value 50 % + quality 50 %)
    def _pctl(key):
        # NaN EXCLU du classement (06/10) : une donnée absente n'a pas de rang.
        # `sorted` sur des NaN rend un ordre arbitraire — et une note inventée.
        connus = [r for r in rows if r[key] == r[key]]
        order = sorted(connus, key=lambda r: r[key])
        n = len(order)
        return {r["symbol"]: (i + 1) / n for i, r in enumerate(order)}
    pv, pq = _pctl("_val"), _pctl("_qual")
    for r in rows:
        v, q = pv.get(r["symbol"]), pq.get(r["symbol"])
        score = None if v is None or q is None else round((v * 0.5 + q * 0.5) * 100, 1)
        r["score"] = score
        mos = r["margin_of_safety"]
        r["rating"] = ("n/d" if score is None
                       else "BUY" if (mos is not None and mos > 0.20 and score >= 50)
                       else "SELL" if (score < 35 or (mos is not None and mos < -0.20))
                       else "HOLD")
        del r["_val"], r["_qual"]
    # rang sectoriel relatif (1 = meilleur de son secteur) — valorisation sector-neutral
    from collections import defaultdict
    by_sec: dict = defaultdict(list)
    for r in rows:
        by_sec[r["sector"]].append(r)
    for sec_rows in by_sec.values():
        notes = [x for x in sec_rows if x["score"] is not None]
        notes.sort(key=lambda x: x["score"], reverse=True)
        for rank, r in enumerate(notes, 1):
            r["sector_rank"] = f"{rank}/{len(notes)}"
        for r in sec_rows:
            r.setdefault("sector_rank", "n/d")
    # NOTE TECHNIQUE + premium/discount sectoriel (PER vs médiane secteur) + note combinée
    from statistics import median

    from packages.indicators.technical_score import technical_rating
    sec_pers: dict = {}
    for r in rows:
        sec_pers.setdefault(r["sector"], []).append(r["per_raw"])
    sec_med = {s: median([p for p in v if p > 0]) if any(p > 0 for p in v) else 0.0
               for s, v in sec_pers.items()}
    for r in rows:
        tech = technical_rating([b.close for b in (data or {}).get(r["symbol"], [])])
        r["tech_score"] = tech["score"]
        r["tech_label"] = tech["label"]
        med = sec_med.get(r["sector"], 0.0)
        r["sector_premium"] = round(r["per_raw"] / med - 1.0, 3) if med > 0 and r["per_raw"] > 0 else None
        r["combined_score"] = (None if r["score"] is None else   # fond. + technique
                               round(0.6 * r["score"] + 0.4 * r["tech_score"], 1))
        del r["per_raw"]
    rows.sort(key=lambda r: (r["combined_score"] is not None,     # non notés : fin
                             r["combined_score"] or 0.0), reverse=True)
    buys = sum(1 for r in rows if r["rating"] == "BUY")
    return {"available": True, "source": src, "n": len(rows), "buys": buys, "rows": rows,
            "total_equities": len(all_eq), "capped": capped,
            "method": "Score = rang percentile value (earnings+FCF yield) 50 % + quality "
                      "(ROIC+marge+conversion FCF) 50 % · DCF FCFF pour la marge de sécurité."}


def _investor_section(symbols: list, acmap: dict, names: dict, sector_of: dict) -> dict:
    """Ranking « grands investisseurs » (Graham/Fisher/Thiel/Schwab). Actions/ETF uniquement."""
    from packages.fundamentals.investor_scores import investor_scores
    from packages.fundamentals.provider import degrade_prior

    prov, src = _fund_provider()
    if prov is None:
        return {"available": False, "reason": src}
    all_eq = [s for s in symbols if acmap.get(s) in ("equity", "etf")]
    cap = 40 if src.startswith("FMP") else (80 if src.startswith("yfinance") else 2000)

    def _rows(provider, universe):
        out = []
        for s in universe:
            try:
                f = provider.get(s)
            except Exception:  # noqa: BLE001
                f = None
            if f is None:
                continue
            sec = sector_of.get(s, "")
            gp = getattr(provider, "get_prior", None)
            prev = gp(s) if callable(gp) else degrade_prior(f)
            out.append({"symbol": s, "name": names.get(s, ""), "sector": sec,
                        **investor_scores(f, sec, prev)})
        return out

    rows = _rows(prov, all_eq[:cap])               # plus de repli synthétique (06/10)
    if not rows:
        return {"available": False, "reason": SANS_SOURCE_REELLE}
    rows.sort(key=lambda r: r["overall"], reverse=True)
    return {"available": True, "source": src, "n": len(rows), "rows": rows,
            "method": "Scores 0-100 par doctrine (% de critères respectés) : Graham (value défensive), "
                      "Fisher (qualité-croissance), Thiel (moat/monopole), Schwab (4ᵉ révolution). "
                      "Overall = moyenne des 4."}
