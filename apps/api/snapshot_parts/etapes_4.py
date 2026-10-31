"""Étapes 25 à 32 de `build_snapshot` (ADR-0220).

Extrait TEL QUEL de `apps/api/snapshot.py` le 31/10 (règle des 400 lignes par fichier) : le
texte des définitions n'a pas changé. `apps/api/snapshot.py` reste la façade et ré-exporte
chaque nom, donc `from apps.api.snapshot import X` fonctionne comme avant.
"""

from __future__ import annotations

from apps.api import payloads as PL
from apps.api.snapshot_parts.compte import _account_compare, _courbes_bots_tiers
from apps.api.snapshot_parts.divers import (
    _essais_de_recherche,
    _psr_dsr,
    _vol_annualisee,
)
from apps.api.snapshot_parts.prix import _curve_stats
from packages.portfolio.benchmark import relative_metrics
from packages.portfolio.correlation import cluster, correlation_matrix
from packages.portfolio.metrics import returns_from_equity
from packages.portfolio.review import expert_review
from packages.portfolio.risk_metrics import risk_metrics as risk_metrics_fn
from packages.portfolio.stress import mc_projection, monte_carlo


def _sb_25(sb) -> None:
    """Étape 25/39 de `build_snapshot` — texte d'origine ; lit et écrit `sb`."""
    _dash_dates, _index_core_info, _live = sb._dash_dates, sb._index_core_info, sb._live
    _preset_alloc, _preset_markers = sb._preset_alloc, sb._preset_markers
    _qqq_closes, _qqq_pct, _real_markers = sb._qqq_closes, sb._qqq_pct, sb._real_markers
    data = sb.data
    # symboles cliquables = alloc preset + positions/ordres RÉELS + symboles tradés par le preset
    _chart_syms = ({o["symbol"] for o in _preset_alloc}
                   | {p.get("symbol") for p in _live["real"]["positions"]}
                   | {o.get("symbol") for o in _live["real"].get("trades", [])}
                   | set(_preset_markers.keys()) | set(_real_markers.keys())) - {""}
    _chart_series = {}
    for s in _chart_syms:
        b = data.get(s)
        if not b:
            continue
        mks = (_preset_markers.get(s) or []) + (_real_markers.get(s) or [])
        mks = [m for m in mks if m.get("t")]
        if mks:                                          # couvre depuis le 1er signal (sinon il est
            first = min(m["t"] for m in mks)             # hors fenêtre et invisible sur le graphe)
            idx = next((i for i, x in enumerate(b) if x.ts.isoformat()[:10] >= first), max(0, len(b) - 500))
            bb = b[max(0, idx - 10):][-2600:]
        else:
            bb = b[-500:]
        _chart_series[s] = [{"t": x.ts.isoformat()[:10], "o": round(x.open, 4), "h": round(x.high, 4),
                             "l": round(x.low, 4), "c": round(x.close, 4), "v": round(x.volume, 0)} for x in bb]
    # bougies RÉELLES Bitmart pour les positions/ordres crypto (absents de YAHOO.db)
    for _sym, _bars in (_live["real"].get("crypto", {}).get("ohlcv", {}) or {}).items():
        if _bars and _sym not in _chart_series:
            _chart_series[_sym] = _bars
    # le cœur QQQ n'est pas dans l'univers → courbe cliquable depuis ses closes réels
    if _index_core_info.get("enabled") and _qqq_pct > 0 and len(_qqq_closes) > 1:
        _cc = [round(float(c), 4) for c in _qqq_closes[-500:]]
        _cd = _dash_dates[-len(_cc):] if len(_dash_dates) >= len(_cc) else []
        if _cd:
            _chart_series["QQQ"] = [{"t": d[:10], "o": c, "h": c, "l": c, "c": c, "v": 0}
                                    for d, c in zip(_cd, _cc)]
    # PERF PAR COMPTE — PRIORITÉ AUX DONNÉES RÉELLES (historique Alpaca / suivi equity quotidien).
    # Repli "modèle" (backtest du sleeve) UNIQUEMENT si le compte n'est pas connecté.
    sb._chart_series = _chart_series


def _sb_26(sb) -> None:
    """Étape 26/39 de `build_snapshot` — texte d'origine ; lit et écrit `sb`."""
    _pe = sb._pe
    from packages.execution.equity_history import series as _eq_series
    def _note_churn(capital: float | None) -> dict:
        """L'annotation de churn, LUE SUR DISQUE et jamais calculée ici.

        Le rapport vient de l'historique du courtier — un appel réseau, avec des clés
        que
        le build public n'a pas. `make churn` le mesure une fois par jour et le dépose ;
        on se contente de le relire. Cache absent ⇒ « NON MESURÉ », ce qui ne se confond
        pas avec « aucun churn » : c'est toute la valeur de l'annotation.
        """
        try:
            from packages.execution.annotation_churn import annotation, lire_cache
            rap, quand = lire_cache()
            return annotation(rap, capital, quand)
        except Exception as e:  # noqa: BLE001 — une note ne fait pas tomber une courbe
            return {"applicable": False, "mesure": False,
                    "motif": f"annotation indisponible ({type(e).__name__}: {e})"}

    def _broker_perf(bd: dict, broker_key: str, model_curve: list | None) -> dict:
        if bd.get("ok"):                                   # compte connecté → on veut du RÉEL
            rc = bd.get("history") or []                   # Alpaca portfolio history (réel)
            if len(rc) < 10:
                rc = _eq_series(broker_key)                # sinon suivi quotidien persistant
            if len(rc) >= 10:
                return {**_curve_stats([p["v"] for p in rc], compte_reel=True,
                                       dates=[str(p.get("t", ""))[:10] for p in rc]),
                        "curve": rc, "source": "réel",
                        "churn": _note_churn(float(rc[-1].get("v") or 0.0))}
            return {"available": False, "source": "réel-court",
                    "note": "Compte récent : historique réel en cours de constitution "
                            "(quelques jours de suivi nécessaires)."}
        if model_curve:                                    # non connecté → modèle (backtest sleeve)
            return {**_curve_stats([p["v"] for p in model_curve]), "curve": model_curve, "source": "modèle"}
        return {"available": False}

    _eq_model = ([{"t": d, "v": v} for d, v in zip(_pe["dates"], _pe["equity"])]
                 if _pe.get("available") else None)
    sb._broker_perf, sb._eq_model, sb._note_churn = _broker_perf, _eq_model, _note_churn


def _sb_27(sb) -> None:
    """Étape 27/39 de `build_snapshot` — texte d'origine ; lit et écrit `sb`."""
    _broker_perf, _dd, _eq_model = sb._broker_perf, sb._dd, sb._eq_model
    _live, _ndx_dates, _ndx_real = sb._live, sb._ndx_dates, sb._ndx_real
    _sp_dates, _sp_real, acmap, data = sb._sp_dates, sb._sp_real, sb.acmap, sb.data
    init_cap, ndx, sp = sb.init_cap, sb.ndx, sb.sp
    from packages.backtest.preset_backtest import preset_equity_daily
    _cr_model = None
    try:
        _crypto_data = {s: b for s, b in data.items()
                        if acmap.get(s) == "crypto" or s.upper().endswith(("USDT", "USDC")) or "/USD" in s.upper()}
        if len(_crypto_data) >= 3:
            _pe_cr = preset_equity_daily(_crypto_data, {}, asset_classes=acmap, dd_target=_dd,
                                         top_k=12, min_names=3, max_weight=0.20, init_cap=init_cap)
            if _pe_cr.get("available"):
                _cr_model = [{"t": d, "v": v} for d, v in zip(_pe_cr["dates"], _pe_cr["equity"])]
    except Exception:  # noqa: BLE001
        pass
    _live["alpaca_perf"] = _broker_perf(_live["real"]["alpaca"], "alpaca", _eq_model)
    from packages.execution.venues import (
        venue_crypto as _vc_here,  # autre portée que le bloc live
    )
    _live["crypto_perf"] = _broker_perf(_live["real"]["crypto"], _vc_here().cle, _cr_model)
    # COMPARAISON COMPTES RÉELS vs INDICES (Alpaca vs Crypto vs S&P vs Nasdaq) pour le dashboard
    _cal_full = [b.ts for b in max(data.values(), key=len)]
    _account_cmp = _account_compare(
        _live["alpaca_perf"].get("curve", []) if _live["alpaca_perf"].get("source") == "réel" else [],
        _live["crypto_perf"].get("curve", []) if _live["crypto_perf"].get("source") == "réel" else [],
        sp if _sp_real else [], ndx if _ndx_real else [],
        _sp_dates if _sp_real else [], _ndx_dates if _ndx_real else [],
        bots=_courbes_bots_tiers())
    # PORTEFEUILLE RÉEL combiné (Alpaca + Bitmart) : courbe d'equity réelle + stats → ligne cliquable
    # du dashboard (réconcilie avec les ORDRES réellement exécutés + positions réelles).
    _alp_c = _live["alpaca_perf"].get("curve", []) if _live["alpaca_perf"].get("source") == "réel" else []
    _cr_c = _live["crypto_perf"].get("curve", []) if _live["crypto_perf"].get("source") == "réel" else []
    _real_portfolio = {"available": False}
    sb._account_cmp, sb._alp_c, sb._cr_c = _account_cmp, _alp_c, _cr_c
    sb._real_portfolio = _real_portfolio


def _sb_28(sb) -> None:
    """Étape 28/39 de `build_snapshot` — texte d'origine ; lit et écrit `sb`."""
    _alp_c, _cr_c, _note_churn = sb._alp_c, sb._cr_c, sb._note_churn
    _real_portfolio = sb._real_portfolio
    if _alp_c or _cr_c:
        _rdates = sorted(set(p["t"][:10] for p in _alp_c) | set(p["t"][:10] for p in _cr_c))

        def _ffill(cv):
            """Report en avant. AVANT le premier point connu → None (et non 0) : un compte pas
            encore suivi n'a pas une valeur nulle, il a une valeur INCONNUE. Le zéro faisait
            bondir la combinaison de toute la valeur du compte le jour de son apparition, saut
            aussitôt compté comme un rendement."""
            m = {p["t"][:10]: p["v"] for p in cv}
            out, last = [], None
            for d in _rdates:
                last = m.get(d, last)
                out.append(last)
            return out
        _a_f, _b_f = _ffill(_alp_c), _ffill(_cr_c)
        # On ne démarre la courbe combinée qu'une fois TOUS les comptes suivis connus : avant,
        # la somme mélangerait un compte mesuré et un compte ignoré.
        _dep = next((i for i, (a, b) in enumerate(zip(_a_f, _b_f))
                     if (a is not None or not _alp_c) and (b is not None or not _cr_c)), None)
        if _dep is None:
            _rdates, _comb = [], []
        else:
            _rdates = _rdates[_dep:]
            _comb = [(a or 0.0) + (b or 0.0) for a, b in zip(_a_f[_dep:], _b_f[_dep:])]
        if len(_comb) >= 2:
            _real_portfolio = {"available": True,
                               "stats": _curve_stats(_comb, compte_reel=True, dates=_rdates),
                               "curve": [{"t": d, "v": round(v, 2)}
                                         for d, v in zip(_rdates, _comb, strict=False)],
                               # La courbe reste CELLE DU COMPTE ; c'est la note qui dit
                               # ce qu'elle porte. Corriger la série publierait une
                               # performance qui n'a jamais eu lieu.
                               "churn": _note_churn(_comb[-1])}
    sb._real_portfolio = _real_portfolio


def _sb_29(sb) -> None:
    """Étape 29/39 de `build_snapshot` — texte d'origine ; lit et écrit `sb`."""
    _edge_proven, cb_syms = sb._edge_proven, sb.cb_syms
    conviction_sec, cov, full_universe = sb.conviction_sec, sb.cov, sb.full_universe
    optimal = sb.optimal
    # BLACK-LITTERMAN : prior équipondéré + vues = conviction z-scorée → poids postérieurs
    try:
        import numpy as _np2

        from packages.portfolio.black_litterman import (
            black_litterman,
            views_from_scores,
        )
        _wm = _np2.array([1.0 / len(cb_syms)] * len(cb_syms))
        if _edge_proven:                         # ticket #7 : vues seulement si edge prouvé
            _conv = {r["symbol"]: r.get("conviction") for r in conviction_sec.get("rows", [])}
            _scores = [_conv.get(s) if _conv.get(s) is not None else float("nan") for s in cb_syms]
            _P, _Q = views_from_scores(_scores)
        else:                                    # sinon : prior pur (aucune vue) = risk-parity-like
            _P, _Q = _np2.zeros((0, len(cb_syms))), _np2.zeros(0)
        optimal["black_litterman"] = black_litterman(cov, _wm, _P, _Q)["weights"]
    except Exception:  # noqa: BLE001
        pass
    # AUDIT BIAIS DU SURVIVANT (honnêteté des backtests longs)
    try:
        from packages.data.survivorship import survivorship_audit
        _uni_syms = [m["symbol"] if isinstance(m, dict) else m for m in full_universe]
        data_sec_extra = survivorship_audit(_uni_syms)
    except Exception:  # noqa: BLE001
        data_sec_extra = None
    sb.data_sec_extra = data_sec_extra


def _sb_30(sb) -> None:
    """Étape 30/39 de `build_snapshot` — texte d'origine ; lit et écrit `sb`."""
    agg, attr, benches, clusters = sb.agg, sb.attr, sb.benches, sb.clusters
    comp, corr, equity, limits, mc = sb.comp, sb.corr, sb.equity, sb.limits, sb.mc
    multi_strategy, optimal, recommended = sb.multi_strategy, sb.optimal, sb.recommended
    rel, rets, risk_budget, rm = sb.rel, sb.rets, sb.risk_budget, sb.rm
    stress, syms = sb.stress, sb.syms
    # === PORTEFEUILLE & ANALYSE — COHÉRENT avec l'ALLOCATION DE PRODUCTION (preset + cœur QQQ) ===
    # Remplace l'analyse du swing legacy (Sharpe 0.17 / maxDD -53 % / revue 28 — hors-sujet) par
    # la même boîte à outils appliquée à ce qui est RÉELLEMENT alloué/tradé. Garde-fou : repli swing.
    _port_payload = {**comp, "metrics": PL.metrics_payload(equity),
                     "benchmarks": PL.benchmark_comparison(equity, benches), "strategy_label": "swing (legacy)",
                     "analysis": {"relative": rel, "risk": rm, "monte_carlo": mc,
                                  "mc_projection": mc_projection(rets, horizon=252, start_value=100.0, seed=1),
                                  "attribution": attr, "correlation": PL.correlation_payload(syms, corr, clusters),
                                  "risk_budget": risk_budget, "limits": limits, "stress": stress,
                                  "optimal_allocation": optimal, "recommended_allocation": recommended,
                                  "review": PL.review_payload(expert_review({**agg, **comp["totals"]})),
                                  "multi_strategy": multi_strategy}}
    sb._port_payload = _port_payload


def _sb_31(sb) -> None:
    """Étape 31/39 de `build_snapshot` — texte d'origine ; lit et écrit `sb`."""
    _index_core_info, _mc_pct, _pe = sb._index_core_info, sb._mc_pct, sb._pe
    _preset_alloc, _qqq_pct, bench_px = sb._preset_alloc, sb._qqq_pct, sb.bench_px
    clusters, corr, data, ml_scores = sb.clusters, sb.corr, sb.data, sb.ml_scores
    names, optimal, recommended = sb.names, sb.optimal, sb.recommended
    risk_budget, stance_by, syms = sb.risk_budget, sb.stance_by, sb.syms
    from packages.portfolio.garch import fit_garch
    from packages.portfolio.risk_advanced import cornish_fisher_var, ewma_vol
    from packages.portfolio.var_backtest import backtest_var
    from packages.regime.vol_regime import vol_regime
    _pl = (" + ".join([f"{int(round(_qqq_pct*100))}% QQQ"]*(_qqq_pct > 0)
           + [f"{int(round(_mc_pct*100))}% TOP10"]*(_mc_pct > 0)
           + [f"{int(round((1-_index_core_info['core_pct'])*100))}% preset"])
           if _index_core_info.get("enabled") else "preset (risk-parity + DD-target)")
    _pr = [{"symbol": r["symbol"], "name": names.get(r["symbol"], r["symbol"]), "sector": r["sector"],
            "asset_class": r["asset_class"], "current_value": r["notional"], "qty": r.get("qty", 0.0),
            "weight_pct": r["weight"], "broker": r.get("broker", ""), "side": "long",
            "avg_price": r.get("price", 0.0), "last": r.get("price", 0.0), "pnl": 0.0, "pnl_pct": 0.0,
            "stance": stance_by.get(r["sector"], "neutral"), "ml_score": ml_scores.get(r["symbol"])}
           for r in _preset_alloc]
    _pt = sum(r["current_value"] for r in _pr) or 1.0
    _pcomp = {"rows": _pr, "totals": {"current_value": round(_pt, 2), "n_positions": len(_pr),
              "exposure_pct": 1.0, "pnl": 0.0, "pnl_pct": 0.0, "cost_basis": round(_pt, 2)}}
    _peq = _pe["equity"]; _prt = returns_from_equity(_peq)
    _prm = risk_metrics_fn(_prt)
    _pv = _prm.get("var_95", 0.0); _prm["var_horizons"] = [{"days": h, "var_95": round(_pv*(h**0.5), 4)} for h in (1, 10, 21)]
    _prm["var_cornish_fisher_95"] = cornish_fisher_var(_prt, 0.95); _prm["vol_ewma"] = ewma_vol(_prt)
    _prm["garch"] = fit_garch(_prt); _prm["var_backtest"] = backtest_var(_prt, _prm.get("var_95", 0.0), alpha=0.95)
    _prm["vol_regime"] = vol_regime(_prt, window=20)
    # Le panneau « mesures de risque » affiché est CELUI-CI : il ne calculait
    # ni PSR ni DSR, et le front rendait les clés absentes « 0,0 % ». Une
    # valeur manquante s'affichait donc en chiffre — le mode de panne qu'on
    # combat partout ailleurs dans ce fichier.
    _prm.update(_psr_dsr(_prt, _essais_de_recherche()))
    _prm.update(_vol_annualisee(_prm))
    _prel = relative_metrics(_peq, bench_px); _pmc = monte_carlo(_prt, seed=1)
    _psy = [r["symbol"] for r in sorted(_pr, key=lambda x: -x["current_value"]) if r["symbol"] in data][:12]
    _pcorr_payload, _prb_payload, _popt, _prec = PL.correlation_payload(syms, corr, clusters), risk_budget, optimal, recommended
    sb._pcomp, sb._pcorr_payload, sb._peq, sb._pl = _pcomp, _pcorr_payload, _peq, _pl
    sb._pmc, sb._popt, sb._pr, sb._prb_payload = _pmc, _popt, _pr, _prb_payload
    sb._prec, sb._prel, sb._prm, sb._prt, sb._psy = _prec, _prel, _prm, _prt, _psy
    sb._pt = _pt


def _sb_32(sb) -> None:
    """Étape 32/39 de `build_snapshot` — texte d'origine ; lit et écrit `sb`."""
    _dd_eff, _pcorr_payload, _popt = sb._dd_eff, sb._pcorr_payload, sb._popt
    _pr, _prb_payload, _prec, _prm = sb._pr, sb._prb_payload, sb._prec, sb._prm
    _psy, _pt, data, recommended = sb._psy, sb._pt, sb.data, sb.recommended
    from packages.portfolio.construction import build_target
    from packages.portfolio.factor_risk import pca_risk
    from packages.portfolio.optimize import (
        equal_risk_contribution,
        hrp_weights,
        min_variance_weights,
    )
    from packages.portfolio.risk_budget import covariance, risk_contributions
    if len(_psy) >= 2:
        _prb_by = {s: returns_from_equity([b.close for b in data[s]]) for s in _psy}
        _ps, _pc = correlation_matrix({k: list(v) for k, v in _prb_by.items()})
        _pcorr_payload = PL.correlation_payload(_ps, _pc, cluster(_ps, _pc, 0.7))
        _pcb, _pcov = covariance({s: list(_prb_by[s]) for s in _ps})
        _pwn = {r["symbol"]: r["current_value"]/_pt for r in _pr}
        _prbk = risk_contributions([_pwn.get(s, 0.0) for s in _pcb], _pcov)
        _prb_payload = {"symbols": _pcb, "contrib_pct": _prbk["contrib_pct"],
                        "portfolio_vol": _prbk["portfolio_vol"], "diversification_ratio": _prbk["diversification_ratio"]}
        _prm["factor_risk"] = pca_risk({s: list(_prb_by[s]) for s in _ps})
        _popt = {"symbols": _pcb, "current": [round(_pwn.get(s, 0.0), 4) for s in _pcb],
                 "hrp": [round(x, 4) for x in hrp_weights(_pcov)],
                 "min_variance": [round(x, 4) for x in min_variance_weights(_pcov)],
                 "risk_parity": [round(x, 4) for x in equal_risk_contribution(_pcov)]}
        try:                                     # allocation recommandée sur les titres PRESET
            _prec = build_target(_pcb, _pcov, {s: _pwn.get(s, 0.0) for s in _pcb},
                                 dd_target=_dd_eff, band=0.03, max_gross=1.0)
            for _k in ("dd_target_nominal", "dd_target_tail_adjusted", "tail_ratio",
                       "edge_proven", "edge_note", "preset_backtest"):
                if _k in recommended:
                    _prec[_k] = recommended[_k]
        except Exception:  # noqa: BLE001
            _prec = recommended
    _pwn = {r["symbol"]: r["current_value"]/_pt for r in _pr}
    _pws, _pwc = {}, {}
    for r in _pr:
        _pws[r["sector"]] = _pws.get(r["sector"], 0.0) + r["current_value"]/_pt
        _pwc[r["asset_class"]] = _pwc.get(r["asset_class"], 0.0) + r["current_value"]/_pt
    # MÊME RÈGLE QUE LE TABLEAU DE BORD (l. 1928) : un tracker indiciel large
    # n'est pas un risque d'émetteur unique. Ce site d'appel n'avait jamais reçu
    # le correctif d'audit du 06/07 — et c'est LUI que lit le post-mortem
    # (incident_note lit portfolio.analysis.limits), d'où « QQQ 50 % > 20 % »
    # publié tous les jours sur un cœur core-satellite parfaitement conforme.
    _pidx = {r["symbol"] for r in _pr if (r.get("asset_class") or "") == "etf"}
    sb._pcorr_payload, sb._pidx, sb._popt = _pcorr_payload, _pidx, _popt
    sb._prb_payload, sb._prec, sb._pwc, sb._pwn = _prb_payload, _prec, _pwc, _pwn
    sb._pws = _pws
