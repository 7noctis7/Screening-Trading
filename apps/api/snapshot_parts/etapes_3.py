"""Étapes 17 à 24 de `build_snapshot` (ADR-0220).

Extrait TEL QUEL de `apps/api/snapshot.py` le 31/10 (règle des 400 lignes par fichier) : le
texte des définitions n'a pas changé. `apps/api/snapshot.py` reste la façade et ré-exporte
chaque nom, donc `from apps.api.snapshot import X` fonctionne comme avant.
"""

from __future__ import annotations

from apps.api import payloads as PL
from apps.api.snapshot_parts.divers import _psr_block
from apps.api.snapshot_parts.live import _live_with_rebalance
from apps.api.snapshot_parts.marche import _attach_rank_scores, _rank_score_map
from apps.api.snapshot_parts.prix import _curve_stats
from packages.common.safe_section import safe_section


def _sb_17(sb) -> None:
    """Étape 17/39 de `build_snapshot` — texte d'origine ; lit et écrit `sb`."""
    _mc_curve, _mc_pct, _mc_real = sb._mc_curve, sb._mc_pct, sb._mc_real
    _mc_top, _mc_w, _mc_weighting = sb._mc_top, sb._mc_w, sb._mc_weighting
    _mktcaps, _pe, _qqq_closes = sb._mktcaps, sb._pe, sb._qqq_closes
    _qqq_pct, _qqq_real, _sm_curve = sb._qqq_pct, sb._qqq_real, sb._sm_curve
    _sm_pct = sb._sm_pct
    _index_core_info = {"enabled": False, "core_pct": 0.0, "symbol": "QQQ+TOP10",
                        "core_type": "multi",
                        "spec": {"qqq": _qqq_pct, "megacap": _mc_pct, "sector_mom": _sm_pct},
                        "core_holdings": _mc_top, "core_weights": _mc_w,
                        "mc_weighting": _mc_weighting, "mktcap_real": bool(_mktcaps),
                        "qqq_is_real": bool(_qqq_real), "mc_is_real": bool(_mc_real)}
    _preset_pure = list(_pe.get("equity", []))           # courbe preset PURE (avant mélange) → sweep
    _preset_pure_dates = list(_pe.get("dates", []))      # dates alignées (pour le stress-test bear)
    _cores = []
    if _qqq_pct > 0 and _qqq_closes and len(_qqq_closes) > 60:
        _cores.append((_qqq_closes, _qqq_pct, "qqq"))
    if _mc_pct > 0 and _mc_curve and len(_mc_curve) > 60:
        _cores.append((_mc_curve, _mc_pct, "megacap"))
    if _sm_pct > 0 and _sm_curve and len(_sm_curve) > 60:
        _cores.append((_sm_curve, _sm_pct, "sector_mom"))
    _total_core = sum(w for _, w, _ in _cores)
    sb._cores, sb._index_core_info = _cores, _index_core_info
    sb._preset_pure, sb._preset_pure_dates = _preset_pure, _preset_pure_dates
    sb._total_core = _total_core


def _sb_18(sb) -> None:
    """Étape 18/39 de `build_snapshot` — texte d'origine ; lit et écrit `sb`."""
    _core_dates, _cores = sb._core_dates, sb._cores
    _index_core_info, _mc_pct, _mc_top = sb._index_core_info, sb._mc_pct, sb._mc_top
    _mc_w, _pe, _preset_pure_dates = sb._mc_w, sb._pe, sb._preset_pure_dates
    _preset_weights, _qqq_closes = sb._preset_weights, sb._qqq_closes
    _qqq_pct, _sm_holds, _sm_pct = sb._qqq_pct, sb._sm_holds, sb._sm_pct
    _total_core, _tradeable_data = sb._total_core, sb._tradeable_data
    init_cap = sb.init_cap
    from packages.backtest.index_core import blend_equity_multi
    if _pe.get("available") and _cores and 0 < _total_core <= 1.0:
        _blended, _m = blend_equity_multi(
            _pe["equity"], [(c, w, _core_dates.get(k)) for c, w, k in _cores],
            init_cap=init_cap, dates=_pe.get("dates"))                  # PAR DATE (QML-004)
        if _blended:
            _base_stats = _curve_stats(_pe["equity"][-_m:])
            _pe["equity"], _pe["dates"] = _blended, _pe["dates"][-_m:]
            _preset_weights = {s: w * (1.0 - _total_core) for s, w in _preset_weights.items()}
            if _qqq_pct > 0:
                _preset_weights["QQQ"] = _preset_weights.get("QQQ", 0.0) + _qqq_pct
            if _mc_pct > 0 and _mc_top:                   # top-10 réparti PAR market cap (sinon égal)
                _w = _mc_w or {s: 1.0 / len(_mc_top) for s in _mc_top}
                _sw = sum(_w.get(s, 0.0) for s in _mc_top) or 1.0
                for _s in _mc_top:
                    _preset_weights[_s] = _preset_weights.get(_s, 0.0) + _mc_pct * _w.get(_s, 0.0) / _sw
            if _sm_pct > 0 and _sm_holds:                 # momentum sectoriel : équipondéré sur les titres tenus
                _per = _sm_pct / len(_sm_holds)
                for _s in _sm_holds:
                    _preset_weights[_s] = _preset_weights.get(_s, 0.0) + _per
            _index_core_info.update({"enabled": True, "core_pct": round(_total_core, 2),
                                     "components": [{"kind": k, "pct": w} for _, w, k in _cores],
                                     "base_stats": _base_stats,
                                     "blended_stats": _curve_stats(_pe["equity"])})
    _core_px = float(_qqq_closes[-1]) if _qqq_closes else 0.0
    _core_sym = "QQQ"
    # CŒUR MULTI-ACTIFS : clôtures des diversifiants reportées sur l'AXE DE DATES du preset.
    # L'alignement se fait ICI, une fois, à la source — pour que le banc n'ait pas à le refaire
    # (et à le rater). N'a AUCUNE incidence sur la production tant que QUANT_CORE_SPEC ne les
    # cite pas : ce bloc ne fait qu'exposer des séries.
    try:
        from packages.backtest.coeur_multi_actifs import SYMBOLES as _MA_SYMS
        from packages.backtest.coeur_multi_actifs import serie_sur_axe as _serie_axe
        _diversifiants = {_s: _serie_axe(_tradeable_data.get(_s), _preset_pure_dates)
                          for _s in _MA_SYMS if _tradeable_data.get(_s)}
    except Exception:  # noqa: BLE001
        _diversifiants = {}
    sb._core_px, sb._core_sym, sb._diversifiants = _core_px, _core_sym, _diversifiants
    sb._preset_weights = _preset_weights


def _sb_19(sb) -> None:
    """Étape 19/39 de `build_snapshot` — texte d'origine ; lit et écrit `sb`."""
    _dd, _diversifiants, _mc_curve = sb._dd, sb._diversifiants, sb._mc_curve
    _pe, _preset_pure = sb._pe, sb._preset_pure
    _preset_pure_dates, _qqq_closes = sb._preset_pure_dates, sb._qqq_closes
    _qqq_dates, _qqq_pct, _quality = sb._qqq_dates, sb._qqq_pct, sb._quality
    _sm_curve, _tradeable_data, acmap = sb._sm_curve, sb._tradeable_data, sb.acmap
    dates, equity, init_cap, sp = sb.dates, sb.equity, sb.init_cap, sb.sp
    ts_list = sb.ts_list
    # blocs de courbes (preset pur + cœurs) → permet au script make index-core de balayer N'IMPORTE
    # quel ratio instantanément, sur la VRAIE mesure de production (source de vérité unique).
    # `dates` = calendrier du PRESET. `qqq_dates` = celui de QQQ, qui n'est PAS le même
    # (indices vs univers négociable) : les publier séparément est ce qui permet à
    # l'attribution d'apparier par date au lieu de supposer un calendrier commun.
    _ic_curves = {"preset": _preset_pure, "qqq": list(_qqq_closes), "megacap": list(_mc_curve),
                  "sector_mom": list(_sm_curve), "dates": _preset_pure_dates, "sp": list(sp),
                  "qqq_dates": list(_qqq_dates), "diversifiants": _diversifiants}
    # JOURNAL DÉTAILLÉ + P&L du portefeuille de production (cœur QQQ + satellite preset) → justifie
    # la perf affichée (clic « Portefeuille (preset) » sur le dashboard). Prix réels, parts/cash.
    try:
        from packages.backtest.preset_backtest import preset_ledger
        _preset_ledger = preset_ledger(_tradeable_data, _quality, asset_classes=acmap, dd_target=_dd,
                                       band=0.03, init_cap=init_cap, max_trades=6000,
                                       core_closes=list(_qqq_closes) if _qqq_pct > 0 else None,
                                       core_dates=list(_qqq_dates) if _qqq_pct > 0 else None,
                                       core_pct=_qqq_pct, core_sym="QQQ")
    except Exception:  # noqa: BLE001
        _preset_ledger = {"available": False}
    # COURBE DU DASHBOARD = courbe du JOURNAL (exécution discrète réaliste, parts/cash) → le graphe
    # et l'historique des trades RÉCONCILIENT exactement (même source). Repli : blend continu / swing.
    if _preset_ledger.get("available") and len(_preset_ledger.get("equity", [])) > 30:
        _dash_metrics = PL.metrics_payload(_preset_ledger["equity"])
        _dash_equity = [{"t": d, "v": v} for d, v in zip(_preset_ledger["dates"], _preset_ledger["equity"])]
        _dash_dates = _preset_ledger["dates"]
        _dash_eq_curve = _preset_ledger["equity"]
    elif _pe.get("available"):
        _dash_metrics = PL.metrics_payload(_pe["equity"])
        _dash_equity = [{"t": d, "v": v} for d, v in zip(_pe["dates"], _pe["equity"])]
        _dash_dates = _pe["dates"]
        _dash_eq_curve = _pe["equity"]
    else:                                              # repli swing si preset indisponible
        _dash_metrics = PL.metrics_payload(equity)
        _dash_equity = PL.equity_series(equity, ts_list)
        _dash_dates = dates
        _dash_eq_curve = equity
    sb._dash_dates, sb._dash_eq_curve = _dash_dates, _dash_eq_curve
    sb._dash_equity, sb._dash_metrics = _dash_equity, _dash_metrics
    sb._ic_curves, sb._preset_ledger = _ic_curves, _preset_ledger


def _sb_20(sb) -> None:
    """Étape 20/39 de `build_snapshot` — texte d'origine ; lit et écrit `sb`."""
    _core_px, _core_sym, _crypto_weights = sb._core_px, sb._core_sym, sb._crypto_weights
    _dash_eq_curve, _preset_weights = sb._dash_eq_curve, sb._preset_weights
    acmap, comp, init_cap = sb.acmap, sb.comp, sb.init_cap
    portfolio_kpis, w_by_name = sb.portfolio_kpis, sb.w_by_name
    # Honnêteté statistique : PSR sur la courbe affichée (isolé — best-effort).
    _honesty = safe_section("honesty", _psr_block, _dash_eq_curve)
    # Exécution réelle (lit les comptes brokers) — calculée TÔT pour dimensionner chaque poche
    # sur le capital de SON compte (actions ← Alpaca, crypto ← Bitmart).
    _replication = {"available": False}
    # BUDGET DÉCLARÉ des deux poches (QML-023) : crypto ≤ QUANT_CRYPTO_PCT du compte, actions +
    # cœur dans le reste. Avant, leur somme était renormalisée par `run_live` et la part crypto
    # sortait du rapport de deux cibles de volatilité (25 à 56 % mesurés).
    from packages.portfolio.budget_poches import negociables, part_crypto, repartir
    _preset_weights, _crypto_weights = repartir(_preset_weights, negociables(_crypto_weights),
                                                part_crypto())
    _live = _live_with_rebalance(comp["rows"], acmap, portfolio_kpis, w_by_name,
                                 target_weights=_preset_weights, crypto_weights=_crypto_weights)
    _alp_cap = (_live["real"]["alpaca"]["equity"] or 0.0) or init_cap
    _bit_cap = _live["real"]["crypto"]["equity"] or 0.0
    # Allocation PRESET détaillée (page Positions) : 2 poches, chacune sur le capital de son broker
    _preset_alloc = []
    _px_override = {_core_sym: _core_px} if _core_px > 0 else {}

    def _extension(bars) -> dict:
        """Distance aux moyennes mobiles + parcours récent. Diagnostic, jamais un filtre.

        Rien dans la chaîne de production ne regarde ces chiffres pour décider d'acheter : le
        preset classe par score composite puis dimensionne en risk-parity. Les afficher permet
        de voir ce que le classement ne dit pas — qu'un titre retenu peut être très étendu."""
        cl = [b.close for b in (bars or []) if b and b.close and b.close > 0]
        if len(cl) < 60:
            return {"ext_ma50": None, "ext_ma200": None, "ret_20j": None}
        px = cl[-1]
        ma = lambda n: (sum(cl[-n:]) / n) if len(cl) >= n else None  # noqa: E731
        m50, m200 = ma(50), ma(200)
        return {"ext_ma50": round(px / m50 - 1, 4) if m50 else None,
                "ext_ma200": round(px / m200 - 1, 4) if m200 else None,
                "ret_20j": round(px / cl[-21] - 1, 4) if len(cl) > 21 else None}
    sb._alp_cap, sb._bit_cap, sb._crypto_weights = _alp_cap, _bit_cap, _crypto_weights
    sb._extension, sb._honesty, sb._live = _extension, _honesty, _live
    sb._preset_alloc, sb._preset_weights = _preset_alloc, _preset_weights
    sb._px_override, sb._replication = _px_override, _replication


def _sb_21(sb) -> None:
    """Étape 21/39 de `build_snapshot` — texte d'origine ; lit et écrit `sb`."""
    _alp_cap, _crypto_weights = sb._alp_cap, sb._crypto_weights
    _extension, _live, _preset_alloc = sb._extension, sb._live, sb._preset_alloc
    _preset_weights, _px_override, acmap = sb._preset_weights, sb._px_override, sb.acmap
    data, ml_scores, screen_sec = sb.data, sb.ml_scores, sb.screen_sec
    screener, sector_of = sb.screener, sb.sector_of
    from packages.execution.routing import route
    def _alloc_rows(weights, cap, ac_default):
        for s, w in sorted(weights.items(), key=lambda kv: -kv[1]):
            if w <= 0:
                continue
            r = route(s, acmap.get(s, ac_default))
            px = data[s][-1].close if data.get(s) else _px_override.get(s, 0.0)
            notion = round(w * cap, 2)
            _preset_alloc.append({"symbol": s, "sector": sector_of.get(s, ""),
                                  "asset_class": acmap.get(s, ac_default), "broker": r["broker"],
                                  "broker_symbol": r["broker_symbol"], "tradeable": r["tradeable"],
                                  "weight": round(w, 4), "notional": notion, "price": round(px, 2),
                                  "qty": round(notion / px, 4) if px else 0.0,
                                  # EXTENSION : « à acheter » vient d'un CLASSEMENT (score composite)
                                  # et d'un DIMENSIONNEMENT (risk-parity), jamais d'un signal
                                  # d'entrée. Le score contient du momentum : il retient donc des
                                  # titres qui ont DÉJÀ monté. Publier l'extension rend ce fait
                                  # visible au lieu de le laisser deviner sur le graphe.
                                  **_extension(data.get(s))})
    _alloc_rows(_preset_weights, _alp_cap, "equity")     # actions/ETF → capital Alpaca
    # Ère paper (ADR-0029) : la crypto part sur le capital ALPACA, en fraction du compte
    # (QML-023). La valoriser sur Bitmart affichait 0 $ pour des ordres bien réels.
    _alloc_rows(_crypto_weights, _alp_cap, "crypto")
    # rank_score decision-time sur target_orders + preset_alloc (journal legacy=0).
    # Sources : screener / screen / ml — jamais inventé ; clé omise si absent.
    _rscores = _rank_score_map(screener, screen_sec, ml_scores)
    _attach_rank_scores(_live.get("target_orders"), _rscores)
    _attach_rank_scores(_preset_alloc, _rscores)
    # Arch A2 — sleeve swing paper : live.swing_orders (flag OFF → [] ; preset inchangé).
    # Barres = cache `data` (Bar .high/.low/.close) ; candidats screener/screen/preset.
    _swing_cand: list[str] = []
    sb._rscores, sb._swing_cand = _rscores, _swing_cand


def _sb_22(sb) -> None:
    """Étape 22/39 de `build_snapshot` — texte d'origine ; lit et écrit `sb`."""
    _alp_cap, _live, _preset_trades = sb._alp_cap, sb._live, sb._preset_trades
    _preset_weights, _rscores = sb._preset_weights, sb._rscores
    _swing_cand, acmap, data, now = sb._swing_cand, sb.acmap, sb.data, sb.now
    screen_sec, screener = sb.screen_sec, sb.screener
    from packages.execution.swing_sleeve import (
        attach_swing_orders as _attach_swing_orders,
    )
    from packages.execution.swing_sleeve import swing_bars_by_sym as _swing_bars_by_sym
    from packages.execution.swing_sleeve import swing_max_names as _swing_max_names
    from packages.execution.swing_sleeve import (
        swing_paper_enabled as _swing_paper_enabled,
    )
    if _swing_paper_enabled():
        _seen_sw: set[str] = set()
        for _row_src in (
            (screener or {}).get("rows", []) or [],
            (screen_sec or {}).get("rows", []) or [],
        ):
            for _r in _row_src:
                _s = (_r or {}).get("symbol") if isinstance(_r, dict) else None
                if _s and _s not in _seen_sw:
                    _seen_sw.add(_s); _swing_cand.append(_s)
        for _s in (_preset_weights or {}):
            if _s and _s not in _seen_sw:
                _seen_sw.add(_s); _swing_cand.append(_s)
        # plafond scan : éviter detecter sur tout l'univers ; max_names borne le résultat
        _swing_cand = _swing_cand[: max(_swing_max_names() * 20, 50)]
    _attach_swing_orders(
        _live,
        bars_by_sym=_swing_bars_by_sym(_swing_cand, data),
        equity_nav=float(_alp_cap or 0.0),
        ts_decision=now.isoformat(),
        rank_scores=_rscores,
        asset_class_by_sym=acmap,
    )
    # Séries OHLC pour les graphiques cliquables (Positions/Trades/Réel) — bornées (~500 barres)
    # MARQUEURS achat/vente du PRESET (par symbole) → fléchés sur le graphe technique des pages
    # Trades & Positions, exactement aux dates des rebalancements (corrige l'absence de signaux).
    _preset_markers: dict[str, list] = {}
    for _t in (_preset_trades.get("trades", []) if _preset_trades.get("available") else []):
        _preset_markers.setdefault(_t["symbol"], []).append(
            {"t": _t["date"][:10], "side": "buy" if _t["side"] == "BUY" else "sell"})
    # MARQUEURS RÉELS (depuis les ordres exécutés Alpaca/Bitmart) → pages Positions & Trades RÉELLES
    _real_markers: dict[str, list] = {}
    sb._preset_markers, sb._real_markers = _preset_markers, _real_markers


def _sb_23(sb) -> None:
    """Étape 23/39 de `build_snapshot` — texte d'origine ; lit et écrit `sb`."""
    _live, _real_markers = sb._live, sb._real_markers
    for _o in _live["real"].get("trades", []):
        _sym = _o.get("symbol", "")
        if _sym:
            _real_markers.setdefault(_sym, []).append(
                {"t": str(_o.get("date", ""))[:10], "side": "buy" if _o.get("side") == "buy" else "sell"})


def _sb_24(sb) -> None:
    """Étape 24/39 de `build_snapshot` — texte d'origine ; lit et écrit `sb`."""
    _live, _preset_alloc, acmap, data = sb._live, sb._preset_alloc, sb.acmap, sb.data
    held, names, sector_of = sb.held, sb.names, sb.sector_of
    sentiment_sec = sb.sentiment_sec
    import os as _os
    if _os.environ.get("QUANT_NEWS") == "1":
        from packages import sentiment as _Snews
        from packages.sentiment.portefeuille import score_momentum as _momentum
        _pf_syms, _seen = [], set()
        for _s in ([p.get("symbol") for p in _live["real"]["positions"]]
                   + [o["symbol"] for o in _preset_alloc] + list(held)):
            if _s and _s not in _seen:
                _seen.add(_s); _pf_syms.append(_s)
        _pf_syms = _pf_syms[:30]

        def _yahoo_sym(sym: str) -> str:               # crypto "BTC/USDT" → "BTC-USD" pour le flux Yahoo
            if acmap.get(sym) == "crypto" or "/" in sym:
                return sym.split("/")[0].upper() + "-USD"
            return sym
        _new_rows = []
        for _s in _pf_syms:
            _r = _Snews.news_sentiment(_yahoo_sym(_s))
            _score, _n, _heads = _r["score"], _r["n"], _r["headlines"]
            if _n == 0:                                # repli momentum (hors-ligne) — cohérent
                _b = data.get(_s)
                _score = (_momentum([b.close for b in _b]) if _b else None) or 0.0
            _new_rows.append({"symbol": _s, "name": names.get(_s, ""), "sector": sector_of.get(_s, ""),
                              "score": _score, "label": _Snews.label_of(_score), "n_news": _n,
                              "headlines": _heads[:5]})
        if _new_rows:
            sentiment_sec["rows"] = _new_rows
            sentiment_sec["portfolio_driven"] = True
            _mood = round(sum(r["score"] for r in _new_rows) / len(_new_rows), 4)
            sentiment_sec["market_mood"] = _mood
            sentiment_sec["market_label"] = _Snews.label_of(_mood)
            sentiment_sec["source"] = "news RSS — recentré sur ton portefeuille (positions réelles + preset)"
