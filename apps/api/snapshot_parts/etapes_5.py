"""Étapes 33 à 39 de `build_snapshot` (ADR-0220).

Extrait TEL QUEL de `apps/api/snapshot.py` le 31/10 (règle des 400 lignes par fichier) : le
texte des définitions n'a pas changé. `apps/api/snapshot.py` reste la façade et ré-exporte
chaque nom, donc `from apps.api.snapshot import X` fonctionne comme avant.
"""

from __future__ import annotations

from apps.api import payloads as PL
from apps.api.snapshot_parts.compte import _earnings_risk
from apps.api.snapshot_parts.divers import (
    _crypto_cockpit_section,
    _intro_section,
    _ticker_section,
)
from apps.api.snapshot_parts.marche import (
    _VIX_NON_CALIBRE,
    _data_section,
    _vix_playbook,
)
from apps.api.snapshot_parts.univers import (
    _SECTEUR_INCONNU,
    _SECTEURS_VEHICULE,
    _universe_section,
)
from packages.common.safe_section import safe_section
from packages.execution.rebalance_plan import min_ligne as _min_ligne
from packages.portfolio.review import expert_review
from packages.portfolio.stress import mc_projection
from packages.reporting.bench_curves import bench_series


def _sb_33(sb) -> None:
    """Étape 33/39 de `build_snapshot` — texte d'origine ; lit et écrit `sb`."""
    _pcomp, _pcorr_payload, _peq = sb._pcomp, sb._pcorr_payload, sb._peq
    _pidx, _pl, _pmc, _popt = sb._pidx, sb._pl, sb._pmc, sb._popt
    _port_payload, _prb_payload, _prec = sb._port_payload, sb._prb_payload, sb._prec
    _prel, _prm, _prt, _pwc, _pwn = sb._prel, sb._prm, sb._prt, sb._pwc, sb._pwn
    _pws, benches, multi_strategy = sb._pws, sb.benches, sb.multi_strategy
    from packages.portfolio.scenarios import hedge_suggestion, scenario_analysis
    from packages.risk.limits import concentration_report
    _plim = concentration_report(_pwn, _pws, max_name=0.20, max_sector=0.40,
                                 index_names=_pidx,
                                 index_sectors=_SECTEURS_VEHICULE,
                                 secteur_inconnu=_SECTEUR_INCONNU)
    _pstress = {"scenarios": scenario_analysis(_pwc), "hedge": hedge_suggestion(_pwc, target_max_loss=-0.15)}
    _pagg = {**PL.metrics_payload(_peq), **_prel, **_prm, **_pmc}
    _port_payload = {**_pcomp, "metrics": PL.metrics_payload(_peq),
                     "benchmarks": PL.benchmark_comparison(_peq, benches), "strategy_label": _pl,
                     "analysis": {"relative": _prel, "risk": _prm, "monte_carlo": _pmc,
                                  "mc_projection": mc_projection(_prt, horizon=252, start_value=100.0, seed=1),
                                  "correlation": _pcorr_payload, "risk_budget": _prb_payload,
                                  "limits": _plim, "stress": _pstress, "optimal_allocation": _popt,
                                  "recommended_allocation": _prec,
                                  "review": PL.review_payload(expert_review({**_pagg, **_pcomp["totals"]})),
                                  "multi_strategy": multi_strategy}}
    sb._port_payload = _port_payload


def _sb_34(sb) -> None:
    """Étape 34/39 de `build_snapshot` — texte d'origine ; lit et écrit `sb`."""
    _audit_report, _cov_cache_stats = sb._audit_report, sb._cov_cache_stats
    _live, _preset_ledger, _replication = sb._live, sb._preset_ledger, sb._replication
    all_trades, data_mode, init_cap = sb.all_trades, sb.data_mode, sb.init_cap
    last_bar, now, start, symbols = sb.last_bar, sb.now, sb.start, sb.symbols
    # ÉCART DE RÉPLICATION : combien du compte réel ne suit PAS le modèle, et quels ordres le
    # réduiraient. Sans ce chiffre, la table « modèle vs réel » laisse croire à un écart de
    # PERFORMANCE là où il y a un écart de COMPOSITION (cf. packages/portfolio/replication).
    try:
        from packages.portfolio.replication import plan_convergence
        _pos_reelles = _live["real"].get("positions", []) or []
        _eq_reel = float(_live["real"].get("equity") or 0.0)
        if not _eq_reel:                       # repli : capital investi (le courtier n'a pas répondu)
            _eq_reel = sum(float(p.get("market_value") or 0.0) for p in _pos_reelles)
        _modele_pos = (_preset_ledger.get("open_positions") or []) if _preset_ledger.get("available") else []
        if _modele_pos and _pos_reelles and _eq_reel > 0:
            _replication = plan_convergence(_modele_pos, _pos_reelles, _eq_reel,
                                            plancher=_min_ligne())
    except Exception:  # noqa: BLE001 — diagnostic, jamais bloquant
        _replication = {"available": False}
    _meta = {
        "generated_at": now.isoformat(),
        "last_bar": last_bar.isoformat(),
        "period_start": start.isoformat(),
        "delay_minutes": 15,                 # flux différé 15 min (EOD/synthétique)
        "mode": data_mode,
        "audit": _audit_report,              # rapport d'intégrité PwC (None si QUANT_AUDIT inactif)
        "cov_cache": _cov_cache_stats,       # hit-rate du cache de covariance (gain réel en prod)
        "data_synthetic": data_mode.startswith("synthetic"),
        "data_warning": ("⚠️ DONNÉES FACTICES (synthétiques) — démo UI uniquement, NE PAS "
                         "décider ni backtester dessus. Branche QUANT_PRICE_DB."
                         if data_mode.startswith("synthetic") else None),
        "strategy": "swing",
        "initial_capital": init_cap,
        "universe_size": len(symbols),
        "traded_assets": len({t.instrument for t in all_trades}),
        "n_trades": len(all_trades),
        "profile": "offensif · moyen-long terme",
    }
    sb._meta, sb._replication = _meta, _replication


def _sb_35(sb) -> None:
    """Étape 35/39 de `build_snapshot` — texte d'origine ; lit et écrit `sb`."""
    _cac_dates, _cac_real, _dash_equity = sb._cac_dates, sb._cac_real, sb._dash_equity
    _sp_dates, _sp_real, cac = sb._sp_dates, sb._sp_real, sb.cac
    instruments, sp, trade_stats = sb.instruments, sb.sp, sb.trade_stats
    # SECTION INTRO — chiffres du rideau d'entrée, DÉRIVÉS de la même courbe
    # que le tableau de bord. Rien n'est saisi à la main : un nombre recopié
    # dans un composant se détache de ce qu'il mesure — cf. le « −9 % » de la
    # landing, issu d'un run `backtest-preset` sur fenêtre courte quand la
    # production affiche −25,3 %. Régénéré à chaque snapshot.
    # RÉFÉRENCE RÉELLE OU AUCUNE. `sp` retombe sur une série SYNTHÉTIQUE quand l'indice
    # n'est pas en base (`_sp_syn`). Comparer la courbe du robot à un S&P 500 inventé
    # serait le mensonge le plus efficace du site : une légende « S&P 500 », une courbe
    # crédible, et rien derrière. Le reste du dashboard fait déjà ce tri (`_sp_real`
    # garde les dates) ; l'intro doit le faire aussi. Sans référence réelle, elle
    # affiche notre seule courbe et le dit.
    _intro = _intro_section(_dash_equity, trade_stats,
                            _sp_dates if _sp_real else [], sp if _sp_real else [],
                            instruments,
                            autres_indices={"CAC 40": (
                                _cac_dates if _cac_real else [],
                                cac if _cac_real else [])})
    sb._intro = _intro


def _sb_36(sb) -> None:
    """Étape 36/39 de `build_snapshot` — texte d'origine ; lit et écrit `sb`."""
    _account_cmp, _cac_dates, _cac_real = sb._account_cmp, sb._cac_dates, sb._cac_real
    _dash_dates, _dash_equity = sb._dash_dates, sb._dash_equity
    _dash_metrics, _honesty = sb._dash_metrics, sb._honesty
    _index_core_info, _live, _macro_real = sb._index_core_info, sb._live, sb._macro_real
    _macro_sources, _mc_pct, _ndx_dates = sb._macro_sources, sb._mc_pct, sb._ndx_dates
    _ndx_real, _pe, _qqq_pct = sb._ndx_real, sb._pe, sb._qqq_pct
    _real_portfolio, _replication = sb._real_portfolio, sb._replication
    _sp_dates, _sp_real, cac, expo = sb._sp_dates, sb._sp_real, sb.cac, sb.expo
    init_cap, last_bar, ndx, regime = sb.init_cap, sb.last_bar, sb.ndx, sb.regime
    sp = sb.sp
    # TABLEAU DE BORD — en deux morceaux (règle des 50 lignes), même ordre de clés.
    _dash_a = {
        "as_of": last_bar.isoformat(),
        "regime": {**PL.regime_payload(regime, expo), "macro_real": _macro_real,
                   "macro_sources": _macro_sources},
        "metrics": _dash_metrics,                 # PRESET (production), pas le swing legacy
        "honesty": _honesty,                       # PSR / honnêteté statistique (manifeste)
        "equity": _dash_equity,
        "account_compare": _account_cmp,           # comptes réels (Alpaca/Crypto) vs S&P/Nasdaq
        "real_portfolio": _real_portfolio,         # courbe RÉELLE combinée (Alpaca+Bitmart) + stats
        "real_trades": _live["real"].get("trades", []),     # ordres RÉELS exécutés (journal réel)
        "real_positions": _live["real"].get("positions", []),  # positions RÉELLES + P&L
        # ÉCART DE RÉPLICATION CHIFFRÉ + plan d'ordres. La table « modèle vs réel » montrait
        # l'écart sans le mesurer ni dire quoi en faire : on lisait « +158 % contre −1,1 % »
        # et on en concluait une sous-performance, alors que c'est une différence de
        # COMPOSITION (une seule ligne commune) et de DURÉE de détention.
        "replication": _replication,
        "index_core": _index_core_info,            # cœur(s) indiciel(s) + satellite preset
        "strategy_label": (
            " + ".join([f"{int(round(_qqq_pct*100))}% QQQ"] * (_qqq_pct > 0)
                       + [f"{int(round(_mc_pct*100))}% TOP10"] * (_mc_pct > 0)
                       + [f"{int(round((1-_index_core_info['core_pct'])*100))}% preset"])
            if _index_core_info.get("enabled")
            else ("preset (risk-parity + DD-target)" if _pe.get("available") else "swing")),
        # Les dates des indices voyagent avec leurs cours : sans elles la courbe du
        # benchmark était tracée sur le calendrier de l'equity (`bench_series`).
        "benchmarks": bench_series(
            {"S&P 500": (sp, _sp_dates if _sp_real else []),
             "Nasdaq 100": (ndx, _ndx_dates if _ndx_real else []),
             "CAC 40": (cac, _cac_dates if _cac_real else [])},
            _dash_dates, init_cap),
    }
    sb._dash_a = _dash_a


def _sb_37(sb) -> None:
    """Étape 37/39 de `build_snapshot` — texte d'origine ; lit et écrit `sb`."""
    _alp_cap, _bit_cap, _chart_series = sb._alp_cap, sb._bit_cap, sb._chart_series
    _dash_dates, _preset_alloc = sb._dash_dates, sb._preset_alloc
    _preset_diag, _preset_markers = sb._preset_diag, sb._preset_markers
    _real_markers, _vix_is_real, comp = sb._real_markers, sb._vix_is_real, sb.comp
    held, n, portfolio_kpis = sb.held, sb.n, sb.portfolio_kpis
    position_markers, position_series = sb.position_markers, sb.position_series
    trade_stats, vix, vix_now = sb.trade_stats, sb.vix, sb.vix_now
    _dash_b = {
        "dates": _dash_dates,
        "positions": comp["rows"], "totals": comp["totals"],
        "preset_allocation": _preset_alloc,        # allocation PRESET (production) → page Positions
        # Journal des étages : dit POURQUOI l'allocation est vide.
        "preset_diagnostic": _preset_diag.as_dict(),
        # Plancher de ligne PUBLIÉ : le front l'affichait en dur de son côté. Deux sources
        # pour un même seuil, c'est une dérive garantie au premier changement.
        "min_position": _min_ligne(),
        "alloc_capital": {"alpaca": round(_alp_cap, 2), "crypto": round(_bit_cap, 2),
                          "total": round(_alp_cap + _bit_cap, 2)},  # base réelle par compte
        "chart_series": _chart_series,             # OHLC cliquables (preset + positions réelles)
        "portfolio": portfolio_kpis,
        "position_series": position_series,
        "position_markers": position_markers,
        "preset_markers": _preset_markers,         # signaux achat/vente du preset (par symbole)
        "real_markers": _real_markers,             # signaux achat/vente RÉELS (ordres brokers)
        "earnings_risk": _earnings_risk(held),
        "trade_stats": trade_stats,
        # PROVENANCE DU VIX — publiée, jamais devinée (31/08).
        #
        # Quand ni `^VIX` ni `VIX` ne donnent une série FRAÎCHE (≥250 barres, ≤7 j),
        # `_vix_series()` fabrique une série synthétique. Le graphe le savait déjà
        # (`_vix_d`/`_vix_v` sont vidés si `_vix_is_real` est faux) — mais le
        # KPI, le playbook et la série étaient publiés SANS distinction. Un
        # « VIX 18 · exposition ×0.8 » sorti d'un générateur aléatoire s'affichait
        # comme une lecture de marché.
        #
        # Le mandat données-réelles tranche : données insuffisantes → on dit
        # UNCALIBRATED, on n'invente pas. Le front rend déjà `null` en « n/d ».
        "vix": vix_now if _vix_is_real else None,
        "vix_reel": bool(_vix_is_real),
        "vix_playbook": (_vix_playbook(vix_now) if _vix_is_real
                         else _VIX_NON_CALIBRE),
        "vix_series": vix[::max(1, n // 240)] if _vix_is_real else [],
    }
    sb._dash_b = _dash_b


def _sb_38(sb) -> None:
    """Étape 38/39 de `build_snapshot` — texte d'origine ; lit et écrit `sb`."""
    _dash_a, _dash_b, _ic_curves = sb._dash_a, sb._dash_b, sb._ic_curves
    _intro, _live, _meta = sb._intro, sb._live, sb._meta
    _port_payload, _preset_ledger = sb._port_payload, sb._preset_ledger
    _preset_trades, acmap, comp = sb._preset_trades, sb.acmap, sb.comp
    conviction_sec, data, data_mode = sb.conviction_sec, sb.data, sb.data_mode
    data_sec_extra, full_universe = sb.data_sec_extra, sb.full_universe
    fundamentals_sec, investors_sec, ml = sb.fundamentals_sec, sb.investors_sec, sb.ml
    recent, screen_sec, screener = sb.recent, sb.screen_sec, sb.screener
    sentiment_sec, themes, trade_stats = sb.sentiment_sec, sb.themes, sb.trade_stats
    _payload = {
        "meta": _meta,
        "intro": _intro,
        "dashboard": {**_dash_a, **_dash_b},
        "screener": screener,
        "screen": screen_sec,
        "crypto_cockpit": safe_section("crypto_cockpit", _crypto_cockpit_section),
        "ticker": safe_section("ticker", _ticker_section, data, acmap),
        "portfolio": _port_payload,
        "trades": [PL.trade_payload(t) for t in recent],
        "open_trades": comp["rows"],
        "trade_stats": trade_stats,
        "preset_trades": _preset_trades,           # journal des rebalancements du preset (production)
        "preset_ledger": _preset_ledger,           # journal détaillé + P&L (justifie la perf du dashboard)
        "index_core_curves": _ic_curves,           # courbes preset/QQQ/megacap → sweeps instantanés
        "universe": safe_section("universe", _universe_section, full_universe),
        "data": {**safe_section("data", _data_section, data, acmap, len(full_universe), data_mode),
                 "fundamentals_provider": fundamentals_sec.get("source", "—"),   # source RÉELLE utilisée (runtime)
                 **({"survivorship": data_sec_extra} if data_sec_extra else {})},
        "themes": themes,
        "ml": ml,
        "sentiment": sentiment_sec,
        "fundamentals": fundamentals_sec,
        "investors": investors_sec,
        "conviction": conviction_sec,
        "live": _live,
    }
    sb._payload = _payload


def _sb_39(sb) -> None:
    """Étape 39/39 de `build_snapshot` — texte d'origine ; lit et écrit `sb`."""
    _payload = sb._payload
    # DATES D'ARRÊTÉ — un seul endroit, calculé sur le payload FINI.
    #
    # Trois dates différentes coexistaient sur le site (18/06 pour le tableau de bord et
    # les données, 04/09 pour les événements et les thèmes, 02/09 pour le tri) sans que
    # rien ne l'explique au lecteur. Certaines divergences sont légitimes — une fenêtre de
    # backtest close n'est pas la donnée du jour, et la crypto cote le samedi quand les
    # actions non — mais le visiteur qui compare deux onglets n'a aucun moyen de le savoir.
    # On publie donc l'inventaire complet : le front peut dire, sur chaque page, de quand
    # datent ses chiffres ET s'ils sont en retard sur le reste du site.
    try:
        from packages.common.coherence_site import dates_d_arrete
        _arretes = dates_d_arrete(_payload)
        _payload["meta"]["arretes"] = _arretes
        _payload["meta"]["arrete_le_plus_frais"] = max(_arretes.values()) if _arretes else None
    except Exception:  # noqa: BLE001 — inventaire d'affichage, jamais bloquant
        _payload["meta"]["arretes"] = {}
        _payload["meta"]["arrete_le_plus_frais"] = None
