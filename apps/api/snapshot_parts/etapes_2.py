"""Étapes 9 à 16 de `build_snapshot` (ADR-0220).

Extrait TEL QUEL de `apps/api/snapshot.py` le 31/10 (règle des 400 lignes par fichier) : le
texte des définitions n'a pas changé. `apps/api/snapshot.py` reste la façade et ré-exporte
chaque nom, donc `from apps.api.snapshot import X` fonctionne comme avant.
"""

from __future__ import annotations

import os as _os_hist
from datetime import UTC, datetime

from apps.api import payloads as PL
from apps.api.snapshot_parts.divers import (
    _conviction_section,
    _env_int,
    _essais_de_recherche,
    _psr_dsr,
    _screen_section,
    _vol_annualisee,
)
from apps.api.snapshot_parts.fondamentaux import (
    _fundamentals_section,
    _investor_section,
)
from apps.api.snapshot_parts.live import _sentiment_section
from apps.api.snapshot_parts.prix import _index_closes_dates
from packages.common.safe_section import safe_section


def _sb_09(sb) -> None:
    """Étape 9/39 de `build_snapshot` — texte d'origine ; lit et écrit `sb`."""
    cb_syms, cov, rets, rets_by, rm = sb.cb_syms, sb.cov, sb.rets, sb.rets_by, sb.rm
    syms, w_by_name = sb.syms, sb.w_by_name
    # --- RISQUE AVANCÉ (VaR Cornish-Fisher, EWMA) + ALLOCATION OPTIMALE (HRP/min-var) ---
    from packages.portfolio.optimize import hrp_weights, min_variance_weights
    from packages.portfolio.risk_advanced import cornish_fisher_var, ewma_vol
    rm["var_cornish_fisher_95"] = cornish_fisher_var(rets, 0.95)
    rm["vol_ewma"] = ewma_vol(rets)
    # GARCH(1,1) vol forecast + backtest de VaR (Kupiec) + risque factoriel (ACP)
    from packages.portfolio.factor_risk import pca_risk
    from packages.portfolio.garch import fit_garch
    from packages.portfolio.var_backtest import backtest_var
    rm["garch"] = fit_garch(rets)
    rm["var_backtest"] = backtest_var(rets, rm.get("var_95", 0.0), alpha=0.95)
    rm["factor_risk"] = pca_risk({s: list(rets_by[s]) for s in syms})
    from packages.portfolio.optimize import equal_risk_contribution
    cur_w = [w_by_name.get(s, 0.0) for s in cb_syms]
    optimal = {"symbols": cb_syms, "current": [round(x, 4) for x in cur_w],
               "hrp": [round(x, 4) for x in hrp_weights(cov)],
               "min_variance": [round(x, 4) for x in min_variance_weights(cov)],
               "risk_parity": [round(x, 4) for x in equal_risk_contribution(cov)]}
    # skfolio (optionnel, qualité recherche) : max-diversification si la lib est installée
    try:
        import numpy as _np

        from packages.portfolio.skfolio_adapter import (
            skfolio_available,
            skfolio_weights,
        )
        if skfolio_available() and len(cb_syms) >= 3:
            _ml = min(len(rets_by[s]) for s in cb_syms)
            if _ml >= 30:
                _mat = _np.array([list(rets_by[s])[-_ml:] for s in cb_syms]).T
                _sk = skfolio_weights(_mat, "max_diversification")
                if _sk and len(_sk) == len(cb_syms):
                    optimal["skfolio_maxdiv"] = _sk
    except Exception:  # noqa: BLE001
        pass
    sb.optimal = optimal


def _sb_10(sb) -> None:
    """Étape 10/39 de `build_snapshot` — texte d'origine ; lit et écrit `sb`."""
    cb_syms, cov, ml, rets, rm = sb.cb_syms, sb.cov, sb.ml, sb.rets, sb.rm
    w_by_name = sb.w_by_name
    # allocation RECOMMANDÉE : risk-parity + bande de non-trading + exposition pilotée par DD-cible
    import os as _os

    from packages.portfolio.construction import (
        build_target,
        tail_adjusted_dd_target,
        vol_target_from_drawdown,
    )
    _dd = float(_os.environ.get("QUANT_DD_TARGET", "0.25"))   # best practice (DSR≈0 → risk-managed) :
    # DD-cible 0.25 (équilibre exposition/DD). 0.15 = max-défensif · 0.45 = agressif. Le cœur QQQ
    # (QUANT_CORE_SPEC) porte la bêta/le rendement ; le preset = satellite à risque maîtrisé.
    # ticket #5 : durcit le DD-cible si les queues sont épaisses (CVaR/VaR > gaussien)
    _tail = (rm.get("cvar_95", 0.0) / rm["var_95"]) if rm.get("var_95") else None
    _dd_eff = tail_adjusted_dd_target(_dd, _tail)
    recommended = build_target(cb_syms, cov, {s: w_by_name.get(s, 0.0) for s in cb_syms},
                               dd_target=_dd_eff, band=0.03, max_gross=1.0)
    recommended["dd_target_nominal"] = _dd
    recommended["dd_target_tail_adjusted"] = round(_dd_eff, 4)
    recommended["tail_ratio"] = round(_tail, 3) if _tail else None
    # ticket #7 : edge gate — sans edge OOS prouvé (DSR/AUC), les signaux ne pilotent PAS l'allocation
    _edge_proven = bool(ml.get("edge_ok")) and (rm.get("dsr", 0.0) or 0.0) >= 0.90
    recommended["edge_proven"] = _edge_proven
    recommended["edge_note"] = ("Edge OOS prouvé : les signaux peuvent incliner l'allocation."
                                if _edge_proven else
                                "Aucun edge OOS prouvé (DSR≈0) → allocation 100 % pilotée par le "
                                "RISQUE (risk-parity), les signaux ne surpondèrent rien.")
    # overlay VOLATILITÉ GÉRÉE (Moreira-Muir) sur les rendements de la stratégie
    from packages.portfolio.vol_managed import vol_managed_backtest
    rm["vol_managed"] = vol_managed_backtest(rets, target_vol=vol_target_from_drawdown(_dd),
                                             window=20, max_leverage=1.0)
    # RÉGIME DE VOLATILITÉ (calme/normal/stress) → multiplicateur d'exposition au-delà du VIX
    from packages.regime.vol_regime import vol_regime
    rm["vol_regime"] = vol_regime(rets, window=20)
    sb._dd, sb._dd_eff, sb._edge_proven = _dd, _dd_eff, _edge_proven
    sb.recommended = recommended


def _sb_11(sb) -> None:
    """Étape 11/39 de `build_snapshot` — texte d'origine ; lit et écrit `sb`."""
    all_trades, broker, comp, data = sb.all_trades, sb.broker, sb.comp, sb.data
    rets, rm = sb.rets, sb.rm
    # Sharpe probabiliste & DÉFLATÉ (garde-fou surapprentissage / essais multiples).
    # CORRIGÉ LE 01/09 : ce bloc lisait `rm.get("sharpe")`, clé que `risk_metrics()`
    # ne produit PAS (var/cvar/vol seulement). Elle manquait donc toujours, le Sharpe
    # valait toujours zéro, et le dashboard publiait « PSR 0,0 % · DSR 0,0 % »
    # puis en tirait « pas d'alpha prouvé ». Le calcul part désormais des
    # RENDEMENTS : la valeur ne peut plus être silencieusement absente.
    _n_trials = _essais_de_recherche()
    rm.update(_psr_dsr(rets, _n_trials))
    rm.update(_vol_annualisee(rm))

    # EVT (risque de queue extrême) + risque de LIQUIDITÉ
    from packages.portfolio.evt import evt_var_es
    from packages.portfolio.liquidity import portfolio_liquidity
    rm["evt"] = evt_var_es(rets, alpha=0.999)
    from packages.portfolio.fragility import fragility as _fragility
    rm["fragility"] = _fragility(rets)            # Taleb : exposition aux extrêmes
    liq_positions = []
    for r in comp["rows"]:
        bars = data.get(r["symbol"], [])[-20:]
        adv = (sum(b.close * b.volume for b in bars) / len(bars)) if bars else 0.0
        liq_positions.append({"symbol": r["symbol"], "value": r["current_value"], "adv": adv})
    rm["liquidity"] = portfolio_liquidity(liq_positions, participation=0.10)
    # séries OHLCV (historique LONG : daily/weekly/monthly agrégés côté front) + marqueurs trades
    open_info = getattr(broker, "open_positions_info", {})
    by_sym_trades = {}
    for t in all_trades:
        by_sym_trades.setdefault(t.instrument, []).append(t)
    position_series, position_markers = {}, {}
    sb.by_sym_trades, sb.open_info = by_sym_trades, open_info
    sb.position_markers, sb.position_series = position_markers, position_series


def _sb_12(sb) -> None:
    """Étape 12/39 de `build_snapshot` — texte d'origine ; lit et écrit `sb`."""
    acmap, all_trades, by_sym_trades = sb.acmap, sb.all_trades, sb.by_sym_trades
    comp, data, equity, ml_scores, n = sb.comp, sb.data, sb.equity, sb.ml_scores, sb.n
    names, open_info, position_markers = sb.names, sb.open_info, sb.position_markers
    position_series, ranked, regime = sb.position_series, sb.ranked, sb.regime
    sector_of, ts_list = sb.sector_of, sb.ts_list
    for r in comp["rows"]:
        s = r["symbol"]
        bars = data[s][-1000:]                         # ~4 ans de daily → agrégeable W/M
        start_t = bars[0].ts
        position_series[s] = [
            {"t": b.ts.isoformat()[:10], "o": round(b.open, 4), "h": round(b.high, 4),
             "l": round(b.low, 4), "c": round(b.close, 4), "v": round(b.volume, 0)} for b in bars]
        marks = []
        oi = open_info.get(s)
        if oi and oi["entry_ts"] >= start_t:
            marks.append({"t": oi["entry_ts"].isoformat()[:10], "side": "buy",
                          "price": round(oi["entry_price"], 4)})
        for tr in by_sym_trades.get(s, []):            # achats/ventes clôturés visibles
            if tr.entry_ts >= start_t:
                marks.append({"t": tr.entry_ts.isoformat()[:10], "side": "buy", "price": round(tr.entry_price, 4)})
            if tr.exit_ts and tr.exit_ts >= start_t:
                marks.append({"t": tr.exit_ts.isoformat()[:10], "side": "sell", "price": round(tr.exit_price, 4)})
        position_markers[s] = marks
    trade_stats = PL.trade_stats_payload(all_trades)
    # turnover annualisé + capacité (best practice : friction & soutenabilité)
    from packages.portfolio.capacity import turnover
    avg_eq = sum(equity) / len(equity) if equity else 0.0
    trade_stats["turnover"] = turnover(all_trades, avg_eq, len(ts_list))
    from packages.execution.costs import cost_assumptions
    trade_stats["cost_assumptions"] = cost_assumptions()   # transparence : coûts par classe (bps)
    # 300 trades les plus récents (couvre la récence + de nombreux actifs)
    recent = sorted(all_trades, key=lambda t: t.entry_ts, reverse=True)[:300]
    dates = [t.isoformat() for t in ts_list]
    screener = PL.screener_payload(ranked, regime.ts)
    for r in screener["rows"]:                    # enrichit le screener du score ML + secteur
        r["ml_score"] = ml_scores.get(r["symbol"])
        r["sector"] = sector_of.get(r["symbol"], "")
    # Screener à FILTRES (packages.screening) — univers réduit aux candidats éligibles.
    screen_sec = safe_section("screen", _screen_section, data, acmap, names, sector_of, n - 1)
    now = datetime.now(UTC)
    last_bar = ts_list[-1]
    sb.dates, sb.last_bar, sb.now, sb.recent = dates, last_bar, now, recent
    sb.screen_sec, sb.screener, sb.trade_stats = screen_sec, screener, trade_stats


def _sb_13(sb) -> None:
    """Étape 13/39 de `build_snapshot` — texte d'origine ; lit et écrit `sb`."""
    acmap, comp, data, equity, held = sb.acmap, sb.comp, sb.data, sb.equity, sb.held
    ml_scores, names, screener = sb.ml_scores, sb.names, sb.screener
    sector_of, symbols, vix = sb.sector_of, sb.symbols, sb.vix
    # dernière valeur FINIE : une barre ^VIX NaN du jour (yfinance) rendait vix_now NaN
    # → playbook/tests cassés. NaN = pas de donnée, on sert la dernière connue.
    vix_now = next((v for v in reversed(vix) if v == v), 0.0)
    init_cap = 10_000
    pf_value = round(equity[-1], 2)
    pf_pnl = round(pf_value - init_cap, 2)
    invested = comp["totals"]["current_value"]
    cash = round(max(0.0, pf_value - invested), 2)         # jamais négatif (pas de levier)
    portfolio_kpis = {
        "value": pf_value, "initial": init_cap, "pnl_abs": pf_pnl,
        "pnl_pct": round(pf_pnl / init_cap, 4), "cash": cash,
        "invested": round(invested, 2),
        "exposure_pct": round(min(1.0, invested / pf_value), 4) if pf_value else 0.0,
        "n_positions": len(comp["rows"]),
    }

    # --- NOTE DE CONVICTION : fusion des lentilles (best practice multi-facteurs) ---
    sentiment_sec = safe_section("sentiment", _sentiment_section, held, names, sector_of, data)
    _cand_eq = list(dict.fromkeys(held + [r["symbol"] for r in screener["rows"]] + symbols))
    fundamentals_sec = safe_section(
        "fundamentals", _fundamentals_section, _cand_eq, acmap, names, sector_of, data)
    investors_sec = safe_section(
        "investors", _investor_section, _cand_eq, acmap, names, sector_of)
    conviction_sec = safe_section(
        "conviction", _conviction_section,
        held, screener, ml_scores, sentiment_sec, fundamentals_sec, investors_sec,
        data, sector_of, names)
    # --- PRESET « best practice » : qualité + risk-parity + DD-target + blackout + no-trade band ---
    # Backtest point-in-time, comparé au swing actuel et à l'équipondéré.
    # QML-022 : jamais de fondamentaux SYNTHÉTIQUES dans l'univers qui part au courtier.
    from packages.backtest.preset_weights import qualite_de_production
    _quality = qualite_de_production(fundamentals_sec)
    sb._quality, sb.conviction_sec = _quality, conviction_sec
    sb.fundamentals_sec, sb.init_cap = fundamentals_sec, init_cap
    sb.investors_sec, sb.portfolio_kpis = investors_sec, portfolio_kpis
    sb.sentiment_sec, sb.vix_now = sentiment_sec, vix_now


def _sb_14(sb) -> None:
    """Étape 14/39 de `build_snapshot` — texte d'origine ; lit et écrit `sb`."""
    _dd, _perimes, _perimes_ac = sb._dd, sb._perimes, sb._perimes_ac
    _quality, acmap, data, equity = sb._quality, sb.acmap, sb.data, sb.equity
    init_cap, real_syms, recommended = sb.init_cap, sb.real_syms, sb.recommended
    from packages.backtest.preset_backtest import preset_backtest

    # UNIVERS NÉGOCIABLE : production restreinte aux instruments (1) négociables par les brokers
    # (actions US + ETF via Alpaca, crypto via Bitmart) ET (2) à DONNÉES RÉELLES uniquement — les
    # symboles en repli synthétique (prix factices, ex. RZLV absent de YAHOO.db) sont EXCLUS de
    # l'allocation/des ordres/des graphes pour ne JAMAIS afficher de prix halluciné.
    from packages.execution.routing import is_tradeable
    _tradeable_data = {s: b for s, b in data.items()
                       if is_tradeable(s, acmap.get(s, "equity")) and s in real_syms}
    if len(_tradeable_data) < 30:                        # garde-fou (mode démo/synthétique) :
        # pas assez de réel → on retombe sur le négociable (la bannière « données factices » prévient)
        _tradeable_data = {s: b for s, b in data.items() if is_tradeable(s, acmap.get(s, "equity"))} or data
    _ro = _os_hist.environ.get("QUANT_RISK_OVERLAY") == "1"   # opt-in overlay risque
    # BACKTEST = négociable + délistés négociables (QML-002). Alignement par date : un titre
    # radié y garde ses dates, et sort au dernier cours connu (`dernier_connu`).
    _bt_ac = {**_perimes_ac, **acmap}
    _bt_data = {**{s: b for s, b in _perimes.items() if is_tradeable(s, _bt_ac.get(s, "equity"))},
                **_tradeable_data}
    preset_bt = preset_backtest(_bt_data, _quality, asset_classes=_bt_ac, swing_equity=equity,
                                dd_target=_dd, band=0.03, risk_overlay=_ro)
    preset_bt["n_delistes_injectes"] = len(_bt_data) - len(_tradeable_data)
    recommended["preset_backtest"] = preset_bt          # rattaché à l'allocation recommandée affichée
    # JOURNAL DES TRADES DU PRESET (rebalancements) → page Trades (remplace le swing legacy)
    from packages.backtest.preset_backtest import preset_trade_log
    _preset_trades = preset_trade_log(_tradeable_data, _quality, asset_classes=acmap,
                                      dd_target=_dd, band=0.03, init_cap=init_cap)
    # ALLOCATION DE PRODUCTION = poids ACTUELS du preset (ce que make live réplique en paper)
    from packages.backtest.preset_weights import preset_latest_weights_explique
    # POURQUOI, pas seulement QUOI. Un satellite vide avait exactement la même
    # sortie qu'un satellite plein de zéros : rien. Le 26/08, trois hypothèses
    # successives sur la cause se sont révélées fausses faute de trace. Le
    # diagnostic est désormais publié à côté des poids.
    _preset_weights, _preset_diag = preset_latest_weights_explique(
        _tradeable_data, _quality, asset_classes=acmap,
        dd_target=_dd, band=0.03, top_k=12, min_weight=0.025)
    # SLEEVE CRYPTO (best practice, risk-parity) — poche SÉPARÉE, dimensionnée sur le capital BITMART.
    # Comptes distincts : les actions sont dimensionnées sur le capital ALPACA, la crypto sur Bitmart.
    _crypto_weights = {}
    sb._bt_ac, sb._bt_data, sb._crypto_weights = _bt_ac, _bt_data, _crypto_weights
    sb._preset_diag, sb._preset_trades = _preset_diag, _preset_trades
    sb._preset_weights, sb._tradeable_data = _preset_weights, _tradeable_data


def _sb_15(sb) -> None:
    """Étape 15/39 de `build_snapshot` — texte d'origine ; lit et écrit `sb`."""
    _crypto_weights, _dd, _quality = sb._crypto_weights, sb._dd, sb._quality
    _tradeable_data, acmap, data = sb._tradeable_data, sb.acmap, sb.data
    init_cap = sb.init_cap
    import os as _os
    try:
        from packages.backtest.crypto_sleeve import crypto_weights
        _crypto_weights = crypto_weights(data, asset_classes=acmap, dd_target=_dd)
    except Exception:  # noqa: BLE001
        pass
    # Courbe d'equity QUOTIDIENNE du preset → c'est ELLE qui pilote le dashboard (le swing est legacy)
    from packages.backtest.preset_backtest import preset_equity_daily
    _pe = preset_equity_daily(_tradeable_data, _quality, asset_classes=acmap, dd_target=_dd, init_cap=init_cap)
    # --- CŒUR(S) INDICIEL(S) + SATELLITE PRESET (multi-cœur) --------------------------------
    # Mélange un/des cœur(s) passif(s) au preset. DÉFAUT : 50% QQQ + 50% preset (meilleur couple
    # rendement/risque sur l'historique réel : Sharpe 0,98 · CAGR 20,3% · maxDD -31% vs preset pur
    # 0,93/17,8%/-34%). Le momentum sectoriel et le top-10 méga-caps sont dominés par QQQ → écartés
    # du défaut (restent activables via la spec). Spec configurable :
    #   QUANT_CORE_SPEC="qqq:0.5"            (défaut)
    #   QUANT_CORE_SPEC="qqq:0.15,megacap:0.10" / "sector_mom:0.25"   (le reste = preset)
    _spec_raw = _os.environ.get("QUANT_CORE_SPEC", "qqq:0.5")
    _spec: dict[str, float] = {}
    for _part in _spec_raw.split(","):
        if ":" in _part:
            _k, _, _v = _part.partition(":")
            try:
                _spec[_k.strip().lower()] = max(0.0, float(_v))
            except ValueError:
                pass
    _qqq_pct, _mc_pct, _sm_pct = _spec.get("qqq", 0.0), _spec.get("megacap", 0.0), _spec.get("sector_mom", 0.0)
    # market caps (sidecar) → pondération « comme un vrai indice »
    _mktcaps = {}
    try:
        from packages.data.market_cap import load_market_caps
        _mktcaps = load_market_caps()
    except Exception:  # noqa: BLE001
        pass
    sb._crypto_weights, sb._mc_pct, sb._mktcaps = _crypto_weights, _mc_pct, _mktcaps
    sb._pe, sb._qqq_pct, sb._sm_pct = _pe, _qqq_pct, _sm_pct


def _sb_16(sb) -> None:
    """Étape 16/39 de `build_snapshot` — texte d'origine ; lit et écrit `sb`."""
    _bt_ac, _bt_data, _mc_pct = sb._bt_ac, sb._bt_data, sb._mc_pct
    _mktcaps, _perimes_sect, _qqq_pct = sb._mktcaps, sb._perimes_sect, sb._qqq_pct
    _tradeable_data, acmap, end = sb._tradeable_data, sb.acmap, sb.end
    init_cap, ndx, sector_of, start = sb.init_cap, sb.ndx, sb.sector_of, sb.start
    # cœur ETF (QQQ) et cœur top-10 méga-caps
    # Les DATES de QQQ voyagent avec ses cours : sans elles, l'attribution comparait
    # deux calendriers par position (bêta 0,006 publié — cf. `_index_closes_dates`).
    _qqq_closes, _qqq_dates, _qqq_real = (
        _index_closes_dates(["QQQ", "^NDX", "^IXIC"], start, end, ndx)
        if _qqq_pct > 0 else ([], [], False))
    _mc_curve, _mc_top, _mc_w, _mc_real, _mc_weighting = [], [], {}, False, "—"
    # Calendrier de CHAQUE cœur, pour l'apparier au preset par date (QML-004).
    _core_dates: dict = {"qqq": list(_qqq_dates)}
    if _mc_pct > 0:
        from packages.backtest.megacap import megacap_equity_daily
        # PANIER RÉGLABLE (QUANT_MEGACAP_TOP, défaut 10). Le classement reste
        # POINT-IN-TIME : panier reclassé tous les 63 jours, pondéré à la date t
        # pour le rendement t→t+1. Prendre le top-N d'AUJOURD'HUI et le rejouer
        # sur onze ans serait un look-ahead massif — NVDA ne pesait rien en 2015.
        _mc_top_n = max(int(_env_int("QUANT_MEGACAP_TOP", 10)), 2)
        _mc = megacap_equity_daily(_tradeable_data, asset_classes=acmap, init_cap=init_cap,
                                   top_n=_mc_top_n, market_caps=_mktcaps or None)
        if _mc.get("available"):
            _mc_curve, _mc_top = _mc["equity"], _mc.get("current_top", [])
            _core_dates["megacap"] = _mc.get("dates")
            _mc_w, _mc_real, _mc_weighting = _mc.get("current_weights", {}), True, _mc.get("weighting", "—")
    # cœur MOMENTUM SECTORIEL — TOUJOURS calculé (pour le sweep `make index-core`), activé en prod
    # seulement si présent dans la spec (QUANT_CORE_SPEC="sector_mom:0.25").
    _sm_curve, _sm_holds, _sm_secs = [], [], []
    try:
        from packages.backtest.sector_momentum import sector_momentum_equity_daily
        _sm = sector_momentum_equity_daily(          # délistés inclus (QML-002)
            _bt_data, {**_perimes_sect, **sector_of}, asset_classes=_bt_ac, init_cap=init_cap)
        if _sm.get("available"):
            _sm_curve = _sm["equity"]
            _core_dates["sector_mom"] = _sm.get("dates")
            _sm_holds, _sm_secs = _sm.get("current_holdings", []), _sm.get("current_sectors", [])
    except Exception:  # noqa: BLE001
        pass
    sb._core_dates, sb._mc_curve, sb._mc_real = _core_dates, _mc_curve, _mc_real
    sb._mc_top, sb._mc_w, sb._mc_weighting = _mc_top, _mc_w, _mc_weighting
    sb._qqq_closes, sb._qqq_dates, sb._qqq_real = _qqq_closes, _qqq_dates, _qqq_real
    sb._sm_curve, sb._sm_holds = _sm_curve, _sm_holds
