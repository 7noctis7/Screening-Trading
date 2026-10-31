"""Sections diverses : screening, PSR/DSR, cockpit crypto, ticker, intro, conviction.

Extrait TEL QUEL de `apps/api/snapshot.py` le 31/10 (règle des 400 lignes par fichier) : le
texte des définitions n'a pas changé. `apps/api/snapshot.py` reste la façade et ré-exporte
chaque nom, donc `from apps.api.snapshot import X` fonctionne comme avant.
"""

from __future__ import annotations

from apps.api.snapshot_parts.base import ROOT
from apps.api.snapshot_parts.prix import _r


def _conviction_section(held: list, screener: dict, ml_scores: dict, sentiment: dict,
                        fundamentals: dict, investors: dict, data: dict, sector_of: dict,
                        names: dict) -> dict:
    """Fusionne toutes les lentilles en une NOTE DE CONVICTION + allocation pilotée par conviction
    et contrôlée par le risque (inverse-vol, plafonnée). Best practice multi-facteurs, poids égaux."""
    from packages.strategies.conviction import conviction_rank, conviction_weights

    fund_by = {r["symbol"]: r.get("combined_score") for r in fundamentals.get("rows", [])}
    sent_by = {r["symbol"]: r.get("score") for r in sentiment.get("rows", [])}
    inv_by = {r["symbol"]: r.get("overall") for r in investors.get("rows", [])}
    cand = list(dict.fromkeys(list(held) + [r["symbol"] for r in screener.get("rows", [])]
                              + list(ml_scores)))[:40]
    signals: dict[str, dict] = {}
    vol: dict[str, float] = {}
    for s in cand:
        bars = data.get(s)
        if not bars or len(bars) < 80:
            continue
        c = [b.close for b in bars]
        trend = c[-1] / c[-63] - 1 if len(c) > 63 else 0.0          # momentum 3 mois (point-in-time)
        rets = [c[i] / c[i - 1] - 1 for i in range(1, len(c))][-252:]
        import numpy as _np
        vol[s] = float(_np.std(rets) * (252 ** 0.5)) if rets else 0.0
        signals[s] = {
            "trend": trend,
            "ml": ml_scores.get(s),
            "fundamental": (fund_by.get(s) / 100.0) if fund_by.get(s) is not None else None,
            "sentiment": sent_by.get(s),
            "investor": (inv_by.get(s) / 100.0) if inv_by.get(s) is not None else None,
        }
    if len(signals) < 3:
        return {"available": False}
    ranked = conviction_rank(signals)
    w = conviction_weights(ranked, vol, top_n=15, max_weight=0.20)
    # backtest POINT-IN-TIME (technique, sans fuite) : conviction vs équipondéré
    from packages.backtest.conviction_backtest import (
        conviction_backtest,
        multi_lens_backtest,
    )
    backtest = conviction_backtest(data)
    # comparaison des top-10 par LENTILLE (fondamentaux / investisseurs / ML / toutes catégories)
    lens_backtest = multi_lens_backtest(data, {
        "Fondamentaux": fund_by,
        "Investisseurs": inv_by,
        "Signaux ML": ml_scores,
        "Toutes catégories": {r["symbol"]: r["conviction"] for r in ranked},
    }, top_n=10)
    rows = [{"symbol": r["symbol"], "name": names.get(r["symbol"], ""),
             "sector": sector_of.get(r["symbol"], ""), "conviction": r["conviction"],
             **{k: r["components"].get(k) for k in ("trend", "ml", "fundamental", "sentiment", "investor")},
             "target_weight": w.get(r["symbol"], 0.0)}
            for r in ranked[:25]]
    return {"available": True, "rows": rows, "backtest": backtest,
            "lens_backtest": lens_backtest,
            "method": "Note = moyenne des z-scores (poids égaux) de : momentum 3 m, proba ML, "
                      "qualité fondamentale, sentiment. Allocation = conviction × inverse-vol, "
                      "plafonnée à 20 %. Discipline anti-surapprentissage (pas de poids optimisés)."}


def _screen_section(panel: dict, acmap: dict, names: dict, sector_of: dict, t: int) -> dict:
    """Screener à FILTRES (packages.screening) : filtres durs YAML puis tri par composite z-score.
    Complète le 'screener' (ranking pur) en montrant l'univers RÉDUIT aux candidats éligibles."""
    try:
        from packages.screening import ScreeningEngine
        eng = ScreeningEngine.from_yaml(ROOT / "config" / "screening.yaml")
    except Exception as e:  # noqa: BLE001 - jamais bloquant
        return {"available": False, "error": str(e)}
    # INVESTABLE uniquement : on ne propose pas un actif non achetable (indices ^… = régime/benchmark,
    # pas un ordre). Évite les candidats fantômes (ex. ^KS11) dans le screener.
    investable = {s: bars for s, bars in panel.items()
                  if not s.startswith("^") and acmap.get(s) != "index"}
    excluded = len(panel) - len(investable)
    try:
        results = eng.screen(investable, t=t)
    except Exception as e:  # noqa: BLE001
        return {"available": False, "error": str(e)}
    rows = []
    for i, r in enumerate(results[:50], 1):
        rows.append({
            "rank": i, "symbol": r.symbol,
            "name": names.get(r.symbol, r.symbol),
            "asset_class": acmap.get(r.symbol, "equity"),
            "sector": sector_of.get(r.symbol, ""),
            "score": _r(r.score),
            "reason": r.reason,
            "ret_12m": _r(r.metrics.get("ret_12m")),
            "drawdown": _r(r.metrics.get("drawdown_from_high")),
            "dollar_volume": _r(r.metrics.get("dollar_volume"), 0),
        })
    return {
        "available": True,
        "count": len(results),
        "universe_size": len(investable),
        "excluded_non_investable": excluded,
        "filters": [f"{f['metric']} {f.get('op', '>=')} {f.get('value')}" for f in eng.filters],
        "weights": eng.weights,
        "rows": rows,
    }


def _env_int(cle: str, defaut: int) -> int:
    """Entier depuis l'environnement, sans jamais lever : un réglage illisible retombe
    sur le défaut plutôt que d'empêcher le snapshot de se construire."""
    import os
    try:
        return int(os.environ.get(cle, "") or defaut)
    except (TypeError, ValueError):
        return defaut


def _essais_de_recherche(minimum: int = 20) -> int:
    """Essais RÉELS depuis le registre de recherche, pour déflater le Sharpe."""
    try:
        from packages.research.ledger import deflation_params
        n, _ = deflation_params(min_trials=minimum)
        return int(n)
    except Exception:  # noqa: BLE001
        return minimum


def _vol_annualisee(rm: dict) -> dict:
    """`risk_metrics()["vol"]` est un écart-type QUOTIDIEN ; `vol_ewma` et le GARCH sont
    ANNUALISÉS. Le panneau les affichait côte à côte sous des libellés qui disent tous
    « sur un an » : 1,0 % à côté de 13,2 % et 8,4 %, trois chiffres dont un dans une
    autre unité. On publie la version annualisée sous un nom qui dit ce qu'elle est,
    plutôt que de changer le contrat de `risk_metrics`, utilisé ailleurs."""
    v = rm.get("vol")
    return {} if not isinstance(v, (int, float)) else {
        "vol_annualisee": round(float(v) * (252 ** 0.5), 5)}


def _psr_dsr(rendements, n_trials: int) -> dict:
    """PSR/DSR depuis les rendements — absents plutôt que faux si l'échantillon
    est insuffisant."""
    from packages.portfolio.psr import psr_dsr_depuis_rendements
    d = psr_dsr_depuis_rendements(rendements, n_trials=n_trials)
    if not d.get("available"):
        return {"psr": None, "dsr": None, "psr_motif": d.get("motif", "")}
    return {"psr": d["psr"], "dsr": d["dsr"], "psr_n_obs": d["n_obs"],
            "psr_n_trials": d["n_trials"],
            "psr_sharpe_annualise": d["sharpe_annualise"]}


def _psr_block(equity: list) -> dict:
    """Honnêteté statistique (cf. manifeste) : PSR = P(Sharpe vrai > 0) sur la courbe affichée,
    corrigée skew/kurtosis (López de Prado). On assume le DSR≈0 plutôt que de le cacher."""
    import numpy as _np

    from packages.portfolio.psr import probabilistic_sharpe_ratio
    e = _np.asarray(equity, float)
    if e.size < 31:
        return {"available": False}
    r = e[1:] / e[:-1] - 1.0
    sd = float(r.std(ddof=1))
    if sd <= 0:
        return {"available": False}
    sharpe_d = float(r.mean() / sd)
    mu = float(r.mean())
    skew = float(((r - mu) ** 3).mean() / sd ** 3)
    kurt = float(((r - mu) ** 4).mean() / sd ** 4)
    psr = probabilistic_sharpe_ratio(sharpe_d, len(r), skew=skew, kurt=kurt, sr_benchmark=0.0)
    return {
        "available": True,
        "psr": psr,
        "sharpe_annualized": round(sharpe_d * (252 ** 0.5), 2),
        "n_obs": int(len(r)),
        "skew": round(skew, 3),
        "excess_kurtosis": round(kurt - 3.0, 2),
        "note": ("PSR = probabilité que le Sharpe vrai dépasse 0 (corrigé skew/kurtosis). "
                 "DSR multi-essais ≈ 0 → pas d'alpha directionnel prouvé : géré comme béta + risque."),
    }


# Audit 07/15 (réduction 50 %) : sections prediction_markets et crypto_onchain SUPPRIMÉES —
# aucune décision du système ne les consommait (finding siège B : décor, pas signal).


def _crypto_cockpit_section() -> dict:
    """Cockpit crypto marché (CoinGecko + DefiLlama + alternative.me, sans clé).
    Gate QUANT_CRYPTO=1 (réseau) → OFF par défaut (tests/offline). Best-effort."""
    import os
    if os.environ.get("QUANT_CRYPTO") != "1":
        return {"available": False, "reason": "QUANT_CRYPTO!=1"}
    try:
        from packages.data.crypto_market import cockpit
        ck = cockpit()
        ok = (ck.get("global") or {}).get("total_mcap") is not None
        if not ok and not ck.get("gainers"):
            return {"available": False, "reason": "réseau"}
        try:                                   # dérivés (funding multi-CEX) — best-effort
            from packages.data.deriv_normalizer import derivatives
            ck["derivatives"] = derivatives()
        except Exception:  # noqa: BLE001
            ck["derivatives"] = {"available": False}
        from packages.data.crypto_market import accumulation_score
        ck["accumulation"] = accumulation_score(ck)   # contrarian 0-100 (déterministe)
        return {"available": True, **ck}
    except Exception as e:  # noqa: BLE001
        return {"available": False, "reason": str(e)}


_TICKER_STOCKS = ("AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AVGO",
                  "BRK-B", "JPM", "V", "WMT", "MA", "COST", "HD", "NFLX", "AMD",
                  "CRM", "ADBE", "PG")


def _ticker_section(data: dict, acmap: dict, n: int = 20) -> dict:
    """Top actions pour le bandeau ticker : dernière clôture + variation J (build-time).

    Données réelles du build (pas de live actions gratuit/CORS côté navigateur). On prend
    d'abord les méga-caps reconnaissables présentes dans l'univers, puis on COMPLÈTE avec
    les autres actions disponibles jusqu'à `n` (sinon le bandeau resterait vide si l'univers
    ne contient pas ces tickers). Jamais de valeur inventée."""
    def _quote(s: str):
        bars = data.get(s)
        if not bars or len(bars) < 2:
            return None
        last, prev = bars[-1].close, bars[-2].close
        return {"sym": s, "price": round(last, 2),
                "chg": round((last / prev - 1) * 100, 2) if prev else None}

    seen, out = set(), []
    for s in _TICKER_STOCKS:                       # 1) méga-caps reconnaissables
        q = _quote(s)
        if q:
            out.append(q); seen.add(s)
    for s in data:                                 # 2) complète avec les actions dispo
        if len(out) >= n:
            break
        if s in seen or acmap.get(s) != "equity":
            continue
        q = _quote(s)
        if q:
            out.append(q); seen.add(s)
    return {"available": bool(out), "stocks": out[:n]}


def _serie_datee(dates, closes) -> list[dict] | None:
    """`[{t, v}]` — ou `None` si les deux listes ne s'alignent pas.

    Un indice dont les cours et les dates ont des longueurs différentes ne se compare à
    rien : le tracer alignerait des valeurs sur les mauvais jours, et l'écart affiché
    serait faux sans qu'aucune erreur ne se produise.
    """
    if not dates or not closes or len(dates) != len(closes):
        return None
    return [{"t": d, "v": v} for d, v in zip(dates, closes, strict=False)]


def _intro_section(equity, trade_stats, sp_dates, sp_closes, instruments,
                   autres_indices: dict | None = None) -> dict:
    """Assemble la section `intro`. Toute absence de donnée est DITE, jamais comblée."""
    from apps.api.intro_payload import construire
    ref = _serie_datee(sp_dates, sp_closes)
    # PLUSIEURS RÉFÉRENCES, et seulement les RÉELLES. Un indice retombé sur sa série
    # synthétique n'entre pas ici : une courbe inventée tracée à côté d'une vraie ferait
    # une comparaison fausse, et rien à l'écran ne la distinguerait de la bonne.
    references: dict[str, list[dict]] = {}
    if ref:
        references["S&P 500"] = ref
    for nom, (d, c) in (autres_indices or {}).items():
        serie = _serie_datee(d, c)
        if serie:
            references[nom] = serie
    classes: dict[str, int] = {}
    for m in instruments or []:
        k = (m.get("asset_class") or "equity").strip() or "equity"
        classes[k] = classes.get(k, 0) + 1
    univers = {"total": len(instruments or []), "par_classe": classes}
    try:
        return construire({"equity": equity}, trade_stats, univers, reference=ref,
                          references=references or None)
    except Exception as e:  # noqa: BLE001 — l'intro ne doit jamais casser le snapshot
        return {"disponible": False, "motif": f"{type(e).__name__}: {e}"}
