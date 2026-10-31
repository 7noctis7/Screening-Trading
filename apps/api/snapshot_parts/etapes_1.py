"""Étapes 1 à 8 de `build_snapshot` (ADR-0220).

Extrait TEL QUEL de `apps/api/snapshot.py` le 31/10 (règle des 400 lignes par fichier) : le
texte des définitions n'a pas changé. `apps/api/snapshot.py` reste la façade et ré-exporte
chaque nom, donc `from apps.api.snapshot import X` fonctionne comme avant.
"""

from __future__ import annotations

import os as _os_hist
from datetime import UTC, datetime, timedelta

from apps.api import payloads as PL
from apps.api.snapshot_parts.base import _HISTORY_DAYS, ROOT
from apps.api.snapshot_parts.compte import _top_traded
from apps.api.snapshot_parts.marche import _themes_section, _vix_series
from apps.api.snapshot_parts.prix import _index_closes, _index_series, _load_prices
from apps.api.snapshot_parts.univers import (
    _SECTEUR_INCONNU,
    _SECTEURS_VEHICULE,
    _db_full_universe,
    _sector_of,
    _seed_universe,
    contient_des_prix_reels,
    is_real_mode,
)
from packages.backtest.fast_swing import fast_swing_backtest
from packages.common import load_yaml
from packages.common.safe_section import safe_section
from packages.data import data_providers
from packages.execution import CostModel
from packages.ml.edge_transversal import section_ml as _ml_section
from packages.portfolio import attribution
from packages.portfolio.benchmark import relative_metrics
from packages.portfolio.correlation import cluster, correlation_matrix
from packages.portfolio.metrics import returns_from_equity
from packages.portfolio.risk_metrics import risk_metrics as risk_metrics_fn
from packages.portfolio.stress import monte_carlo
from packages.ranking import RankingEngine
from packages.regime import MacroImpactMap, MacroRegimeClassifier, synthetic_macro
from packages.storage import MacroStore


def _sb_01(sb) -> None:
    """Étape 1/39 de `build_snapshot` — texte d'origine ; lit et écrit `sb`."""
    seed = sb.seed
    instruments = _seed_universe()
    symbols = [m["symbol"] for m in instruments]
    acmap = {m["symbol"]: m["asset_class"] for m in instruments}
    names = {m["symbol"]: m["name"] for m in instruments}
    sector_of = {m["symbol"]: _sector_of(m) for m in instruments}
    end = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    start = end - timedelta(days=_HISTORY_DAYS)
    # prix RÉELS (base locale) si disponibles, sinon synthétique sectorisé (cohérence secteurs)
    data, data_mode, real_syms = _load_prices(instruments, sector_of, start, end, seed)
    # NETTOYAGE UNIVERS : écarte les titres PÉRIMÉS (delisted/renommés, ex. FB→META) dont
    # la dernière barre est trop ancienne → plus de 404 ni de cibles fantômes. Seuil RELATIF
    # (vs la barre la plus fraîche) → ne vide jamais l'univers, même hors-ligne.
    # QML-002 : les périmées sont MISES DE CÔTÉ, pas jetées. La production ne les voit pas ;
    # les backtests qui alignent par date (`preset_backtest`, momentum sectoriel) les
    # retrouvent — sans elles, ils ne mesuraient que des survivants.
    _perimes: dict = {}
    _perimes_ac: dict = {}
    _perimes_sect: dict = {}
    if contient_des_prix_reels(data_mode) and data:
        from packages.data.survivorship import separer_perimees
        data, _perimes = separer_perimees(data, jours=10)
        _perimes_ac = {s: acmap.get(s, "equity") for s in _perimes}
        _perimes_sect = {s: sector_of.get(s, "") for s in _perimes}
        for s in _perimes:
            real_syms.discard(s)
    # INTÉGRITÉ DES DONNÉES : si une base réelle est branchée, on RETIRE TOUT symbole en repli
    # synthétique de l'univers de travail → screener, ML, thèmes, conviction, preset, graphes…
    # tournent UNIQUEMENT sur des prix réels (zéro donnée fictive). En mode démo (aucune base),
    # real_syms est vide → on garde le synthétique (la bannière « données factices » prévient).
    if len(real_syms) >= 30:
        instruments = [m for m in instruments if m["symbol"] in real_syms]
        symbols = [m["symbol"] for m in instruments]
        data = {s: data[s] for s in symbols}
        acmap = {s: acmap[s] for s in symbols}
        names = {s: names[s] for s in symbols}
        sector_of = {s: sector_of[s] for s in symbols}
    sb._perimes, sb._perimes_ac, sb._perimes_sect = _perimes, _perimes_ac, _perimes_sect
    sb.acmap, sb.data, sb.data_mode, sb.end = acmap, data, data_mode, end
    sb.instruments, sb.names, sb.real_syms = instruments, names, real_syms
    sb.sector_of, sb.start, sb.symbols = sector_of, start, symbols


def _sb_02(sb) -> None:
    """Étape 2/39 de `build_snapshot` — texte d'origine ; lit et écrit `sb`."""
    data, data_mode, end, instruments = sb.data, sb.data_mode, sb.end, sb.instruments
    real_syms, seed, start, symbols = sb.real_syms, sb.seed, sb.start, sb.symbols
    # --- GATE D'AUDIT (PwC) : avant de bâtir screener/ML/preset sur ces prix, on les audite.
    #   QUANT_AUDIT=strict  → REFUSE de servir des données à anomalie CRITIQUE (lève → l'API sert
    #                         le dernier snapshot sain ; un build corrompu n'atteint jamais l'écran).
    #   QUANT_AUDIT=warn|1  → audite et joint le rapport (`_audit`) au snapshot, sans bloquer.
    #   (défaut désactivé ; n'audite QUE des prix réels — le synthétique de démo n'a pas à passer.)
    #   (défaut = `warn` : audite les prix réels + joint le rapport, sans bloquer ;
    #    `strict` reste opt-in pour le gate CI ; `off` désactive.)
    _audit_report: dict | None = None
    _audit_mode = (_os_hist.environ.get("QUANT_AUDIT", "warn") or "warn").lower()
    if _audit_mode in ("strict", "warn", "1", "true") and real_syms and is_real_mode(data_mode):
        from packages.data.audit import assert_integrity, audit_and_report
        try:
            _ar = audit_and_report(data, universe=symbols)
            _audit_report = _ar.to_dict()
            if _audit_mode == "strict":
                assert_integrity(_ar)             # lève DataIntegrityError si anomalie critique
        except Exception as _ae:                  # noqa: BLE001
            if _audit_mode == "strict":
                raise                             # strict : on propage → l'API garde le snapshot sain
            _audit_report = {"ok": False, "error": str(_ae)}   # warn : best-effort, jamais bloquant

    n = max(len(b) for b in data.values())
    # VIX RÉEL (^VIX) si dispo (base/yfinance), aligné sur n barres ; sinon synthétique.
    _vix_real, _vix_is_real = _index_closes(["^VIX", "VIX"], start, end, [])
    if _vix_is_real and len(_vix_real) >= 50:
        vix = _vix_real[-n:] if len(_vix_real) >= n else [_vix_real[0]] * (n - len(_vix_real)) + _vix_real
    else:
        vix = _vix_series(n, seed)                # repli synthétique (playbook volatilité + modulation)
    full_universe = _db_full_universe() or instruments   # univers EXHAUSTIF (29k tickers si DB)
    sb._audit_report, sb._vix_is_real = _audit_report, _vix_is_real
    sb.full_universe, sb.n, sb.vix = full_universe, n, vix


def _sb_03(sb) -> None:
    """Étape 3/39 de `build_snapshot` — texte d'origine ; lit et écrit `sb`."""
    acmap, data, end, start, vix = sb.acmap, sb.data, sb.end, sb.start, sb.vix
    # --- backtest swing VECTORISÉ sur TOUT l'univers, capital fictif 10 000 $.
    # Profil offensif moyen-long terme : on alloue le cash aux MEILLEURS setups (tri par
    # conviction), exposition modulée par le VIX, positions laissées ouvertes. ---
    broker, journal, equity, ts_list = fast_swing_backtest(
        data, cash=10_000, costs=CostModel(), asset_classes=acmap,
        target_annual_vol=0.30, max_capital_frac=0.15, max_positions=20, max_pct=0.20,
        atr_stop=4.0, rr=6.0, vix=vix, close_at_end=False,
        daily_max_loss=0.06,        # kill-switch : stop des entrées si perte du jour > 6%
        # SUIVEUR RETIRÉ (scripts/sortie_lab.py, 02/09). Il ne protégeait pas les
        # gains, il les COUPAIT. La cible vise +24 ATR ; le suiveur à 5 ATR mordait
        # presque toujours avant, si bien que le 6:1 nominal n'existait pas. Deux runs
        # sur deux jeux de données différents s'accordent sur le SENS : sans suiveur
        # bat trail 5 sur payoff, marge, Sharpe, DSR, espérance et net — et le maxDD
        # s'AMÉLIORE (−27,8 % contre −29,1 %) : la seule objection sérieuse tombe.
        # Le risque par trade est inchangé : le stop initial à 4 ATR tient toujours.
        # NON PROUVÉ pour autant : l'écart de Sharpe reste sous le seuil détectable
        # (±0,27). C'est la cohérence de la famille (trail 3 très mauvais, trail 8
        # intermédiaire, sans suiveur le meilleur) qui décide, pas un point isolé.
        trail_atr=0.0,
        next_open_fills=True,       # exécution à l'ouverture suivante (anti look-ahead)
        # RISQUE CONSTANT à 0,5 % de l'equity par trade (scripts/sizing_lab.py, 01/09).
        # Le notionnel faisait dépendre la taille d'une ligne de combien le carnet
        # était plein ce jour-là : profit factor privé des cinq meilleurs trades à
        # 0,89 — le système devenait PERDANT sans cinq lignes sur 477. À 0,5 % il
        # passe à 1,15 : le résultat ne tient plus à cinq tailles heureuses.
        # CE QUI N'EST PAS PROUVÉ : le gain de Sharpe (0,52 -> 0,66) n'est PAS
        # significatif (p = 0,59) et le net baisse de 9 642 à 6 863 $. On adopte ce
        # réglage pour la ROBUSTESSE, pas la performance — et parce que l'avantage
        # de net du notionnel s'explique par des tailles chanceuses qu'on n'a aucune
        # raison d'attendre à nouveau. Repli : remettre 0.0.
        risque_par_trade=0.005)

    # indices RÉELS (S&P 500 / Nasdaq 100) — calculés TÔT car le régime macro s'en sert
    _sp_syn = [b.close for b in data_providers.create(
        "synthetic", seed=101, drift=0.09, annual_vol=0.16).fetch_ohlcv("S&P 500", "1d", start, end)]
    sb._sp_syn, sb.broker, sb.equity, sb.journal = _sp_syn, broker, equity, journal
    sb.ts_list = ts_list


def _sb_04(sb) -> None:
    """Étape 4/39 de `build_snapshot` — texte d'origine ; lit et écrit `sb`."""
    _sp_syn, _vix_is_real, acmap, data = sb._sp_syn, sb._vix_is_real, sb.acmap, sb.data
    end, start, vix = sb.end, sb.start, sb.vix
    _ndx_syn = [b.close for b in data_providers.create(
        "synthetic", seed=202, drift=0.13, annual_vol=0.22).fetch_ohlcv("Nasdaq 100", "1d", start, end)]
    sp, _sp_dates, _sp_real = _index_series(["^GSPC", "SPX", "SPY"], start, end, _sp_syn)
    ndx, _ndx_dates, _ndx_real = _index_series(["^NDX", "^IXIC", "QQQ"], start, end, _ndx_syn)
    # CAC 40 — troisième repère, pour que la comparaison ne dépende pas du seul indice
    # américain. `_cac_real` commande tout : une série qui n'est pas RÉELLE n'est affichée
    # NULLE PART, ni au dashboard ni dans l'intro. AUCUN repli synthétique n'est fourni
    # (liste vide) — mieux vaut une comparaison absente qu'une courbe inventée tracée à
    # côté d'une vraie, que rien à l'écran ne distinguerait de la bonne.
    # Les symboles sont de VRAIS tickers de l'indice : `CAC` ne désignait rien et `EWQ`
    # est un ETF France, c'est-à-dire un proxy, pas le CAC 40.
    cac, _cac_dates, _cac_real = _index_series(["^FCHI", "PX1", "CAC.PA"], start, end, [])

    # régime macro RÉEL point-in-time : VIX réel + tendance S&P (proxy activité) + FRED (courbe,
    # chômage) si FRED_API_KEY. Repli synthétique UNIQUEMENT si aucune donnée réelle disponible.
    import os as _os_macro
    _fred_key = _os_macro.environ.get("FRED_API_KEY")
    _macro_sources, _macro_real = {"régime": "synthétique (aucune donnée macro réelle dispo)"}, False
    if _vix_is_real or _sp_real or _fred_key:        # au moins une vraie source macro
        from packages.regime.real_macro import real_macro_store
        _cal = [b.ts for b in max(data.values(), key=len)]
        _vix_d = _cal[-len(vix):] if _vix_is_real else []
        _vix_v = vix if _vix_is_real else []
        _sp_d = _sp_dates if _sp_real else []
        _sp_v = sp if _sp_real else []
        ms, _macro_sources, _macro_real = real_macro_store(_vix_v, _vix_d, _sp_v, _sp_d, fred_key=_fred_key)
    if not _macro_real or ms.count() == 0:
        months = int(_HISTORY_DAYS / 30) + 4
        ms = MacroStore(":memory:"); ms.upsert(synthetic_macro(start, months=months))
        _macro_sources, _macro_real = {"régime": "synthétique (aucune donnée macro réelle dispo)"}, False
    regime = MacroRegimeClassifier(ms).classify(end - timedelta(days=2))
    impact = MacroImpactMap(load_yaml(ROOT / "config" / "macro_impact.yaml"))
    expo = impact.exposure_multiplier(regime)

    # ranking / screener sur TOUT l'univers
    ranker = RankingEngine(load_yaml(ROOT / "config" / "factors.yaml"), acmap)
    sb._cac_dates, sb._cac_real, sb._macro_real = _cac_dates, _cac_real, _macro_real
    sb._macro_sources, sb._ndx_dates = _macro_sources, _ndx_dates
    sb._ndx_real, sb._sp_dates, sb._sp_real = _ndx_real, _sp_dates, _sp_real
    sb.cac, sb.expo, sb.ndx, sb.ranker, sb.regime = cac, expo, ndx, ranker, regime
    sb.sp = sp


def _sb_05(sb) -> None:
    """Étape 5/39 de `build_snapshot` — texte d'origine ; lit et écrit `sb`."""
    data, end, equity, journal, n = sb.data, sb.end, sb.equity, sb.journal, sb.n
    names, ndx, ranker, regime = sb.names, sb.ndx, sb.ranker, sb.regime
    sector_of, sp, symbols = sb.sector_of, sb.sp, sb.symbols
    ranked = ranker.rank(data, t=n - 1, regime=regime, top_n=12)

    # benchmark JUSTE = univers équipondéré (buy & hold) → mesure l'alpha actif du swing.
    # (S&P 500 / Nasdaq 100 RÉELS déjà chargés plus haut pour le régime macro.)
    norm = [[b.close / d0[0].close for b in d0] for d0 in (data[s] for s in symbols)]
    eqw = [sum(col) / len(col) * 100 for col in zip(*norm)]
    bench_px = eqw
    benches = {"Univers (équipondéré)": eqw, "S&P 500": sp, "Nasdaq 100": ndx}
    # backtest MULTI-STRATÉGIE sur l'indice équipondéré (tendance/momentum/retour moyenne + ensemble)
    from packages.backtest.multi_strategy import run_multi_strategy
    from packages.common.memo import cached_stage
    # étape PURE (courbe → stratégies) : mémoïsée par contenu → non recalculée si l'indice équipondéré
    # n'a pas changé (pas de nouvelle barre). Repli transparent sur le calcul direct si cache indispo.
    multi_strategy = cached_stage("multi_strategy", [float(x) for x in eqw],
                                  lambda: run_multi_strategy(eqw))

    # --- analyse de portefeuille (mesures relatives, risque, thèmes, ML) ---
    rel = relative_metrics(equity, bench_px)
    rets = returns_from_equity(equity)
    rm = risk_metrics_fn(rets)
    # VaR multi-horizon (mise à l'échelle racine-du-temps) : 1 j / 10 j (Bâle) / 21 j (1 mois)
    _v1 = rm.get("var_95", 0.0)
    rm["var_horizons"] = [{"days": h, "var_95": round(_v1 * (h ** 0.5), 4)} for h in (1, 10, 21)]
    # Monte-Carlo (2000 sims, seedé → déterministe) mémoïsé par contenu : non relancé si les
    # rendements du portefeuille n'ont pas changé (cf. packages/common/memo.py).
    mc = cached_stage("monte_carlo", [float(x) for x in rets], lambda: monte_carlo(rets, seed=1))
    all_trades = journal.all()
    attr = attribution.attribute(all_trades, "strategy")
    agg = {**PL.metrics_payload(equity), **rel, **rm, **mc}
    themes = safe_section("themes", _themes_section, data, sector_of, end)  # isolé
    stance_by = themes.get("stance_by_sector", {})
    ml = safe_section("ml", _ml_section, data, sector_of, names)            # isolé
    ml_scores = ml.get("scores", {}) if ml.get("available") else {}

    # SINGLE SOURCE OF TRUTH : les positions ouvertes pilotent positions/trades/corrélation/graphes
    marks = {s: data[s][-1].close for s in symbols}
    sb.agg, sb.all_trades, sb.attr, sb.bench_px = agg, all_trades, attr, bench_px
    sb.benches, sb.marks, sb.mc, sb.ml, sb.ml_scores = benches, marks, mc, ml, ml_scores
    sb.multi_strategy, sb.ranked, sb.rel, sb.rets = multi_strategy, ranked, rel, rets
    sb.rm, sb.stance_by, sb.themes = rm, stance_by, themes


def _sb_06(sb) -> None:
    """Étape 6/39 de `build_snapshot` — texte d'origine ; lit et écrit `sb`."""
    acmap, broker, data, journal = sb.acmap, sb.broker, sb.data, sb.journal
    marks, ml_scores, names, sector_of = sb.marks, sb.ml_scores, sb.names, sb.sector_of
    stance_by, symbols = sb.stance_by, sb.symbols
    meta_pos = {s: {"asset_class": acmap.get(s), "name": names.get(s)} for s in symbols}
    comp = PL.composition_payload(broker.positions(), marks, meta_pos)
    for r in comp["rows"]:                       # liaison position ↔ secteur/thème + ML
        sec = sector_of.get(r["symbol"], "")
        r["sector"] = sec
        r["stance"] = stance_by.get(sec, "neutral")
        r["ml_score"] = ml_scores.get(r["symbol"])
    held = [r["symbol"] for r in comp["rows"]]
    # corrélation sur LES MÊMES actifs que les positions (cohérence inter-fenêtres)
    corr_syms = held[:12] if len(held) >= 2 else [s for s, _ in _top_traded(journal, 8)] or symbols[:8]
    rets_by = {s: returns_from_equity([b.close for b in data[s]]) for s in corr_syms}
    syms, corr = correlation_matrix({k: list(v) for k, v in rets_by.items()})
    clusters = cluster(syms, corr, 0.7)

    # --- BUDGET DE RISQUE + LIMITES DE CONCENTRATION (best practice buy-side) ---
    from packages.portfolio.risk_budget import covariance, risk_contributions
    invested_now = comp["totals"]["current_value"] or 1.0
    w_by_name = {r["symbol"]: r["current_value"] / invested_now for r in comp["rows"]}
    # Véhicules indiciels larges (cœur core-satellite) : plafond dédié, pas la limite 20 %/nom
    _index_names = {r["symbol"] for r in comp["rows"] if (r.get("asset_class") or "") == "etf"}
    w_by_sector: dict[str, float] = {}
    for r in comp["rows"]:
        w_by_sector[r["sector"]] = w_by_sector.get(r["sector"], 0.0) + r["current_value"] / invested_now
    cb_syms, cov = covariance({s: list(rets_by[s]) for s in syms})  # mêmes actifs que corr
    rb = risk_contributions([w_by_name.get(s, 0.0) for s in cb_syms], cov)
    # diagnostic de conditionnement (qualité du risque) : cov empirique vs régularisée + δ retenu
    _cov_diag: dict = {}
    _cov_cache_stats: dict = {}
    sb._cov_cache_stats, sb._cov_diag = _cov_cache_stats, _cov_diag
    sb._index_names, sb.cb_syms, sb.clusters = _index_names, cb_syms, clusters
    sb.comp, sb.corr, sb.cov, sb.held = comp, corr, cov, held
    sb.invested_now, sb.rb, sb.rets_by, sb.syms = invested_now, rb, rets_by, syms
    sb.w_by_name, sb.w_by_sector = w_by_name, w_by_sector


def _sb_07(sb) -> None:
    """Étape 7/39 de `build_snapshot` — texte d'origine ; lit et écrit `sb`."""
    _cov_cache_stats, _cov_diag, cb_syms = sb._cov_cache_stats, sb._cov_diag, sb.cb_syms
    cov, rb, rets_by, syms = sb.cov, sb.rb, sb.rets_by, sb.syms
    try:
        import numpy as _npd

        from packages.data.engine import (
            auto_ttl_days,
            covariance_diagnostics,
            covariance_matrix,
            ledoit_wolf_shrinkage,
            persist_cov_cache_stats,
            purge_cov_disk_cache,
        )
        purge_cov_disk_cache(auto_ttl_days())              # purge TTL auto-réglé (1×/build)
        _rets = {s: list(rets_by[s]) for s in syms}
        _, _cov_raw = covariance_matrix(_rets, shrink=False)
        _csyms = [s for s in cb_syms if _rets.get(s) and len(_rets[s]) >= 2]
        _m = min(len(_rets[s]) for s in _csyms) if _csyms else 0
        _delta = 0.0
        if _m >= 2:
            _mat = _npd.array([_rets[s][-_m:] for s in _csyms], dtype=float)
            _, _delta = ledoit_wolf_shrinkage(_mat)
        _cov_diag = covariance_diagnostics(_cov_raw, cov, delta=_delta)
        _cov_cache_stats = persist_cov_cache_stats()       # cumul persistant (hit-rate multi-builds)
    except Exception:  # noqa: BLE001 — diagnostic best-effort, jamais bloquant
        _cov_diag = {}
    risk_budget = {"symbols": cb_syms, "contrib_pct": rb["contrib_pct"],
                   "portfolio_vol": rb["portfolio_vol"],
                   "diversification_ratio": rb["diversification_ratio"],
                   "covariance_diagnostics": _cov_diag}
    sb._cov_cache_stats, sb.risk_budget = _cov_cache_stats, risk_budget


def _sb_08(sb) -> None:
    """Étape 8/39 de `build_snapshot` — texte d'origine ; lit et écrit `sb`."""
    _index_names, acmap, comp = sb._index_names, sb.acmap, sb.comp
    invested_now, rets_by, w_by_name = sb.invested_now, sb.rets_by, sb.w_by_name
    w_by_sector = sb.w_by_sector
    from packages.risk.limits import concentration_report
    # #3 audit : la corrélation de stress PILOTE les limites (resserre si diversif faiblit)
    try:
        import numpy as _np_lim

        from packages.portfolio.correlation import conditional_correlation
        from packages.risk.limits import concentration_report_adaptive
        _rb = {k: list(v) for k, v in rets_by.items() if len(v) >= 10}
        _ml = min((len(v) for v in _rb.values()), default=0)
        if len(_rb) >= 2 and _ml >= 10:
            _aligned = {k: v[-_ml:] for k, v in _rb.items()}
            _proxy = [float(x) for x in _np_lim.mean(list(_aligned.values()), axis=0)]
            _corr_cond = conditional_correlation(_aligned, _proxy)
            limits = concentration_report_adaptive(w_by_name, w_by_sector, _corr_cond,
                                                   max_name=0.20, max_sector=0.40,
                                                   index_names=_index_names,
                                                   index_sectors=_SECTEURS_VEHICULE,
                                                   secteur_inconnu=_SECTEUR_INCONNU)
        else:
            limits = concentration_report(w_by_name, w_by_sector, max_name=0.20,
                                          max_sector=0.40, index_names=_index_names,
                                          index_sectors=_SECTEURS_VEHICULE,
                                          secteur_inconnu=_SECTEUR_INCONNU)
    except Exception:  # noqa: BLE001 — repli sur le rapport fixe
        limits = concentration_report(w_by_name, w_by_sector, max_name=0.20,
                                      max_sector=0.40, index_names=_index_names,
                                      index_sectors=_SECTEURS_VEHICULE,
                                      secteur_inconnu=_SECTEUR_INCONNU)

    # --- STRESS-TESTS MACRO + COUVERTURE (axe 11) ---
    from packages.portfolio.scenarios import hedge_suggestion, scenario_analysis
    w_by_class: dict[str, float] = {}
    for r in comp["rows"]:
        ac = acmap.get(r["symbol"], "equity")
        w_by_class[ac] = w_by_class.get(ac, 0.0) + r["current_value"] / invested_now
    stress = {"scenarios": scenario_analysis(w_by_class),
              "hedge": hedge_suggestion(w_by_class, target_max_loss=-0.15)}
    sb.limits, sb.stress = limits, stress
