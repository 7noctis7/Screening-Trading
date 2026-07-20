"""Backtest du PRESET stratégique « best practice » (point-in-time, anti-fuite).

Combine, à chaque rebalancement :
  1. **Tilt qualité** : univers = top-K par score fondamental (statique → neutre vis-à-vis des prix,
     pas de fuite ; c'est un *sleeve* facteur qualité).
  2. **Risk-parity (ERC)** : chaque actif contribue également au risque (covariance trailing).
  3. **DD-target exposure** : exposition brute dimensionnée pour viser un drawdown cible
     (vol-cible ≈ DD/1.6 — anti cash-drag), plafonnée à 100 % (**jamais de levier**) → le reste en cash.
     Tilt momentum (#4) + porte de régime/frein DD (#5/#6) appliqués au gross/poids.
  4. **Earnings blackout (proxy)** : on évite d'entrer juste après un choc binaire (|move 2 j| élevé).
  5. **No-trade band** : on ne bouge un poids que s'il dérive de plus de `band` (turnover ↓).
  6. **Coûts par classe d'actifs** déduits du turnover (réalisme).

Compare le preset à l'équipondéré (bench) et, si fourni, à la courbe du swing. numpy pur, testable.
"""

from __future__ import annotations

import os

import numpy as np

from packages.backtest.conviction_backtest import _stats
from packages.execution.costs import CostModel
from packages.portfolio.optimize import equal_risk_contribution
from packages.portfolio.risk_advanced import ewma_vol
from packages.portfolio.risk_overlay import drawdown_taper


def _cov_annual(win: np.ndarray) -> np.ndarray:
    if win.shape[0] == 1:
        return np.array([[float(win.var()) * 252]])
    try:                                                        # #3 Ledoit-Wolf : covariance shrinkée
        from packages.data.engine import ledoit_wolf_shrinkage  # (n×T) → Σ stabilisée
        cov, _ = ledoit_wolf_shrinkage(win)
        return cov * 252
    except Exception:  # noqa: BLE001 — repli covariance empirique si indispo
        return np.cov(win) * 252


def _regime_mult(mkt: np.ndarray, t: int, *, dd_hard: float = -0.15,
                 dd_soft: float = -0.10, g_dist: float = 0.6,
                 g_below: float = 0.2) -> float:
    """#5 porte de régime + #6 frein de drawdown sur l'indice marché (moyenne univers).
    Plein risque en tendance saine ; coupe en distribution / sous MM200 / gros DD.
    Ne réduit jamais le gross au-dessus de 1. Seuils en kwargs (défauts inchangés) →
    testables en sensibilité (audit) sans changer le comportement de prod."""
    if t < 25:
        return 1.0
    hist = mkt[:t + 1]
    ma = hist[-200:].mean()
    slope = mkt[t] / mkt[t - 20] - 1.0
    peak = float(np.maximum.accumulate(hist)[-1])
    dd = mkt[t] / peak - 1.0 if peak > 0 else 0.0
    if dd < dd_hard:                                       # #6 frein DD : krach → cash
        return 0.0
    g = 1.0 if (mkt[t] > ma and slope > 0) else (g_dist if mkt[t] > ma else g_below)
    if dd < dd_soft:                                           # #6 demi-frein
        g *= 0.5
    return g


def _mom_tilt(A: np.ndarray, t: int, w: np.ndarray, gamma: float = 1.0) -> np.ndarray:
    """#4 incline les poids ERC vers le momentum 12 mois (capte les leaders type NVDA), SANS toucher
    au gross : on renormalise à la même somme. Réduit le « low-vol drag » de l'ERC pur."""
    base = A[:, max(0, t - 252)]
    mom = np.where(base > 0, A[:, t] / base - 1.0, 0.0)
    tilt = np.clip(mom, 0.0, None) ** gamma
    if float(tilt.sum()) <= 0:
        return w
    f = 0.5 + 0.5 * tilt / (tilt.mean() + 1e-9)                  # 0.5×base + 0.5×momentum
    w2 = w * f
    s = float(w2.sum())
    return w2 / s if s > 0 else w


def _breadth(A: np.ndarray, t: int) -> float:
    """#8 ampleur de marché : fraction de l'univers au-dessus de sa MM200 (santé interne du marché).
    Faible breadth = rallye étroit/fragile → on réduit le gross. Data-driven, dans [0,1]."""
    if t < 25:
        return 1.0
    lo = max(0, t - 200)
    above = [A[i, t] > A[i, lo:t].mean() for i in range(A.shape[0]) if t - lo > 5]
    return float(np.mean(above)) if above else 1.0


def _cap_weights(w: np.ndarray, max_weight: float) -> np.ndarray:
    """Plafond de concentration itéré : aucune position > max_weight, excès redistribué
    au prorata des positions libres, puis renormalisation (gross conservé).
    Extrait (audit 07/15) : cette boucle vivait en 3 copies divergentes."""
    for _ in range(3):
        over = w > max_weight
        if not over.any():
            break
        excess = (w[over] - max_weight).sum()
        w[over] = max_weight
        free = ~over & (w > 0)
        if free.any():
            w[free] += excess * w[free] / w[free].sum()
        else:
            break
    s = w.sum()
    return w / s if s > 0 else w


def _adaptive_cap(cov: np.ndarray, max_weight: float, corr_tighten: bool,
                  stress_corr: float = 0.60, tighten: float = 0.5,
                  floor: float = 0.05) -> float:
    """Plafond par nom RESSERRÉ quand la corrélation moyenne de l'univers monte
    (diversification qui s'effondre → le portefeuille devient un pseudo-indice).
    Branche `correlation_aware_caps` (packages/risk/limits) sur le RAIL DE PROD —
    audit 07/15 : « la sophistication était de l'étagère »."""
    if not corr_tighten or cov.shape[0] < 3:
        return max_weight
    d = np.sqrt(np.clip(np.diag(cov), 1e-12, None))
    corr = cov / np.outer(d, d)
    n = corr.shape[0]
    avg = float((corr.sum() - n) / (n * (n - 1)))
    return max(floor, round(max_weight * tighten, 4)) if avg > stress_corr else max_weight


def _price_universe(data: dict, syms: list, lookback: int, top_k: int) -> list:
    """#2 ANTI-FUITE (partagé) : univers = top-K par MOMENTUM prix-only mesuré au DÉBUT de la
    fenêtre commune (aucune info future ; on n'applique JAMAIS le score qualité du JOUR à des dates
    passées). Miroir exact de `preset_backtest(legacy_quality_universe=False)`, réutilisé par les
    fonctions dashboard/ledger (sinon elles ré-introduisent le look-ahead + le biais du survivant)."""
    if len(syms) < 5:
        return syms[:top_k]
    L = min(len(data[s]) for s in syms)
    M = {s: np.asarray([b.close for b in data[s]][-L:], float) for s in syms}
    _s0 = max(lookback, 50)
    sel = {s: float(M[s][_s0 - 1] / M[s][max(0, _s0 - 252 - 1)] - 1)
           for s in syms if len(M[s]) > _s0}
    return (sorted(sel, key=lambda s: sel[s], reverse=True)[:top_k]
            if len(sel) >= 5 else syms[:top_k])


def preset_backtest(data: dict, quality: dict | None = None, asset_classes: dict | None = None,
                    swing_equity: list | None = None, dd_target: float = 0.25, band: float = 0.03,
                    step: int = 21, lookback: int = 120, top_k: int = 30, k_dd: float = 1.6,
                    blackout_move: float = 0.12, regime_gate: bool = True,
                    mom_tilt: bool = True, legacy_quality_universe: bool = False,
                    breadth_gate: bool = True, risk_overlay: bool = False,
                    ro_dd_soft: float = -0.08, ro_dd_hard: float = -0.20,
                    ewma_lam: float = 0.94, max_weight: float | None = None,
                    corr_tighten: bool = False, exec_lag: int = 0) -> dict:
    """`exec_lag` (audit 07/17, M-1) : nb de barres entre la DÉCISION (close t, sur info ≤t)
    et l'EXÉCUTION. 0 = fill au close de la barre de signal (défaut historique — mini
    look-ahead : le close du jour de signal n'est pas exécutable). 1 = fill au close t+1
    (réaliste). La fenêtre de détention est décalée d'autant ; `make preset-lab` chiffre l'écart."""
    syms = [s for s, b in data.items() if b and len(b) > lookback + 2 * step]
    if len(syms) < 5:
        return {"available": False}
    L = min(len(data[s]) for s in syms)
    M = {s: np.asarray([b.close for b in data[s]][-L:], float) for s in syms}
    acmap = asset_classes or {}
    quality = quality or {}

    # #2 ANTI-FUITE : en backtest, le score `quality` est le score ACTUEL → l'appliquer à des dates
    # passées = look-ahead + biais du survivant. On sélectionne donc l'univers par MOMENTUM prix-only
    # mesuré au DÉBUT du backtest (aucune info future). `legacy_quality_universe=True` rétablit l'ancien
    # comportement (fuite — pour comparaison uniquement). En PRODUCTION, le tilt qualité du jour reste légitime.
    if legacy_quality_universe:
        q = {s: quality.get(s) for s in syms if quality.get(s) is not None}
        universe = (sorted(q, key=lambda s: q[s], reverse=True)[:top_k]
                    if len(q) >= 5 else syms[:top_k])
    else:
        _s0 = max(lookback, 50)
        _sel = {s: float(M[s][_s0 - 1] / M[s][max(0, _s0 - 252 - 1)] - 1)
                for s in syms if len(M[s]) > _s0}
        universe = (sorted(_sel, key=lambda s: _sel[s], reverse=True)[:top_k]
                    if len(_sel) >= 5 else syms[:top_k])
    A = np.asarray([M[s] for s in universe])                    # n × L
    mkt = A.mean(axis=0)                                         # indice de marché (porte régime + frein DD)
    rets = A[:, 1:] / A[:, :-1] - 1
    tgt_vol = max(0.0, abs(dd_target)) / k_dd
    per_year = 252.0 / step
    rt = np.asarray([CostModel.for_asset_class(acmap.get(s, "equity")).round_trip_bps / 1e4
                     for s in universe])

    prev_w = np.zeros(len(universe))
    port: list[float] = []
    gross_hist: list[float] = []
    turn = 0.0
    eq_strat, peak_strat = 1.0, 1.0                  # equity stratégie (overlay risque)
    start = max(lookback, 50)
    for t in range(start, L - 1, step):
        win = rets[:, max(0, t - lookback):t]
        if win.shape[1] < 20:
            continue
        cov = _cov_annual(win)
        w = np.asarray(equal_risk_contribution(cov), float)     # risk-parity
        last2 = A[:, t] / A[:, t - 2] - 1                       # blackout : évite le post-choc binaire
        w = np.where(np.abs(last2) > blackout_move, 0.0, w)
        ssum = w.sum()
        w = w / ssum if ssum > 0 else w
        if mom_tilt:                                            # #4 incline vers les leaders (momentum)
            w = _mom_tilt(A, t, w)
        if max_weight:                                          # plafond (adaptatif si corr_tighten)
            w = _cap_weights(w, _adaptive_cap(cov, max_weight, corr_tighten))
        pv = float(np.sqrt(max(0.0, w @ cov @ w)))              # DD-target : exposition pilotée par la vol
        gross = 0.0 if pv <= 0 else min(1.0, tgt_vol / pv)
        if regime_gate:                                         # #5 régime + #6 frein DD (≤ 1, jamais de levier)
            gross *= _regime_mult(mkt, t)
        if breadth_gate:                                        # #8 ampleur de marché (rallye étroit → ↓)
            gross *= float(np.clip(_breadth(A, t) / 0.5, 0.0, 1.0))
        if risk_overlay:                             # overlay : taper DD + vol prévue
            dd_now = eq_strat / peak_strat - 1.0 if peak_strat > 0 else 0.0
            gross *= drawdown_taper(dd_now, ro_dd_soft, ro_dd_hard)
            if pv > 0 and len(port) >= 10:           # EWMA > réalisée → réduire
                fv = ewma_vol(port[-60:], lam=ewma_lam, annualize=int(round(per_year)))
                if fv > pv:
                    gross *= pv / fv
        w = w * gross
        if band > 0 and prev_w.sum() > 0:                       # bande de non-trading
            w = np.where(np.abs(w - prev_w) < band, prev_w, w)
        entry = min(t + exec_lag, L - 1)                        # M-1 : exécution à t+exec_lag
        nxt = min(entry + step, L - 1)
        fwd = A[:, nxt] / A[:, entry] - 1                       # rendement RÉALISÉ après l'exécution
        cost = float((np.abs(w - prev_w) * rt).sum())
        ret_step = float((w * fwd).sum()) - cost
        port.append(ret_step)
        eq_strat *= (1.0 + ret_step)                 # maj equity (taper au pas suivant)
        peak_strat = max(peak_strat, eq_strat)
        turn += float(np.abs(w - prev_w).sum())
        gross_hist.append(float(w.sum()))
        prev_w = w
    if len(port) < 3:
        return {"available": False}

    def _cum(series: list) -> list:
        e = np.cumprod(1 + np.asarray(series, dtype=float))
        return [1.0] + [round(float(x), 4) for x in e]

    out = {"available": True, "step_days": step, "top_k": len(universe),
           "preset": _stats(port, per_year),
           "turnover_annual": round(turn / len(port) * per_year, 2),
           "dd_target": dd_target, "band": band, "target_vol": round(tgt_vol, 4),
           "avg_gross": round(float(np.mean(gross_hist)) if gross_hist else 0.0, 4),
           "curves": {"preset": _cum(port)}}

    # bench équipondéré sur le MÊME univers (apples-to-apples : isole l'apport de la construction
    # risk-parity + DD-target + blackout + band vs un simple équipondéré plein-investi)
    bench = [float((A[:, min(t + step, L - 1)] / A[:, t] - 1).mean())
             for t in range(start, L - 1, step)]
    out["benchmark"] = _stats(bench, per_year)
    out["curves"]["benchmark"] = _cum(bench)

    # swing (depuis sa courbe d'equity), ré-échantillonné sur la même grille
    if swing_equity and len(swing_equity) >= L:
        eq = np.asarray(swing_equity[-L:], float)
        grid = list(range(start, L, step))
        sr = [eq[b] / eq[a] - 1 for a, b in zip(grid[:-1], grid[1:]) if eq[a] > 0]
        if len(sr) >= 3:
            out["swing"] = _stats(sr, per_year)
            out["curves"]["swing"] = _cum(sr)
    return out


def preset_latest_weights(data: dict, quality: dict | None = None, asset_classes: dict | None = None,
                          dd_target: float = 0.35, band: float = 0.03, lookback: int = 120,
                          top_k: int = 30, k_dd: float = 1.6, blackout_move: float = 0.12,
                          max_weight: float = 0.10, min_names: int = 12,
                          regime_gate: bool = True, mom_tilt: bool = True,
                          breadth_gate: bool = True, min_weight: float = 0.025,
                          corr_tighten: bool = True) -> dict:
    """Poids cibles ACTUELS du preset (dernière barre) — pilote la PRODUCTION (make live).

    Même logique que le backtest (qualité top-K -> risk-parity ERC -> DD-target -> blackout), mais
    calculée au dernier point seulement. Renvoie {symbol: poids} (somme <= 1, le reste en cash).
    """
    syms = [s for s, b in data.items() if b and len(b) > lookback]
    if len(syms) < 5:
        return {}
    L = min(len(data[s]) for s in syms)
    M = {s: np.asarray([x.close for x in data[s]][-L:], float) for s in syms}
    quality = quality or {}
    q = {s: quality.get(s) for s in syms if quality.get(s) is not None}
    universe = (sorted(q, key=lambda s: q[s], reverse=True)[:top_k]
                if len(q) >= 5 else syms[:top_k])
    A = np.asarray([M[s] for s in universe])
    mkt = A.mean(axis=0)                                         # indice de marché (porte régime + frein DD)
    rets = A[:, 1:] / A[:, :-1] - 1
    t = L - 1
    win = rets[:, max(0, t - lookback):t]
    if win.shape[1] < 20:
        return {}
    cov = _cov_annual(win)
    w = np.asarray(equal_risk_contribution(cov), float)
    last2 = A[:, t] / A[:, t - 2] - 1
    w_bl = np.where(np.abs(last2) > blackout_move, 0.0, w)
    # n'applique le blackout que s'il laisse un portefeuille DIVERSIFIÉ (sinon on garde tout l'ERC)
    if int((w_bl > 0).sum()) >= min_names:
        w = w_bl
    ssum = w.sum()
    w = w / ssum if ssum > 0 else w
    if mom_tilt:                                                # #4 tilt momentum (avant le plafond)
        w = _mom_tilt(A, t, w)
    # PLAFOND DE CONCENTRATION (rail prod) : resserré ×0,5 si la corrélation moyenne de
    # l'univers dépasse 0,60 (diversification en breakdown → plus de noms imposés).
    w = _cap_weights(w, _adaptive_cap(cov, max_weight, corr_tighten))
    tgt_vol = max(0.0, abs(dd_target)) / k_dd
    pv = float(np.sqrt(max(0.0, w @ cov @ w)))
    gross = 0.0 if pv <= 0 else min(1.0, tgt_vol / pv)
    if regime_gate:                                             # #5 régime + #6 frein DD (production)
        gross *= _regime_mult(mkt, t)
    if breadth_gate:                                            # #8 ampleur de marché (production)
        gross *= float(np.clip(_breadth(A, t) / 0.5, 0.0, 1.0))
    w = w * gross
    w = _concentrate(w, min_weight)     # jette la poussière → moins d'actifs, mieux dimensionnés
    return {universe[i]: round(float(w[i]), 4) for i in range(len(universe)) if w[i] > 1e-4}


def _concentrate(w: "np.ndarray", min_weight: float) -> "np.ndarray":
    """Élimine les positions sous `min_weight` (fraction de l'investi) et redistribue leur poids
    aux survivants → portefeuille CONCENTRÉ sur les meilleures convictions, même gross investi.
    Anti-« poussière » : fini les dizaines de lignes à quelques dollars."""
    inv = float(w.sum())
    if inv <= 0 or min_weight <= 0:
        return w
    w = np.where(w / inv < min_weight, 0.0, w)
    keep = float(w.sum())
    return w * (inv / keep) if keep > 0 else w


def preset_equity_daily(data: dict, quality: dict | None = None, asset_classes: dict | None = None,
                        dd_target: float = 0.35, band: float = 0.03, step: int = 21,
                        lookback: int = 120, top_k: int = 30, k_dd: float = 1.6,
                        blackout_move: float = 0.12, max_weight: float = 0.10, min_names: int = 12,
                        init_cap: float = 10000.0) -> dict:
    """Courbe d'equity QUOTIDIENNE du preset (pour le dashboard) : rebalancement tous les `step`
    jours, accumulation des rendements quotidiens entre deux rebalancements. Renvoie
    {equity:[$], dates:[iso], available}. Univers ANTI-FUITE (momentum prix-only, cf. _price_universe)
    et rendements quotidiens NETS des coûts de turnover (barème par classe d'actifs)."""
    syms = [s for s, b in data.items() if b and len(b) > lookback + step]
    if len(syms) < 5:
        return {"available": False}
    quality = quality or {}  # conservé pour compat API ; PLUS utilisé pour l'univers (anti-fuite, cf. _price_universe)
    universe = _price_universe(data, syms, lookback, top_k)
    # COURBE LA PLUS LONGUE POSSIBLE : on garde les `min_names` titres aux plus longs historiques →
    # la fenêtre remonte aussi loin que le permettent au moins min_names valeurs (au lieu d'un
    # seuil 60 % arbitraire qui coupait la courbe vers ~2021).
    _lens = sorted((len(data[s]) for s in universe), reverse=True)
    _need = _lens[min(min_names, len(_lens)) - 1] if _lens else 0
    universe = [s for s in universe if len(data[s]) >= _need] or universe
    L = min(len(data[s]) for s in universe)
    M = {s: np.asarray([b.close for b in data[s]][-L:], float) for s in universe}
    ref = max(universe, key=lambda s: len(data[s]))
    dts = [b.ts.isoformat() for b in data[ref]][-L:]
    A = np.asarray([M[s] for s in universe])
    rets = A[:, 1:] / A[:, :-1] - 1
    tgt_vol = max(0.0, abs(dd_target)) / k_dd
    start = max(lookback, 50)
    acmap = asset_classes or {}                           # #P0-3 : coûts par classe (fin de l'equity brute)
    rt = np.asarray([CostModel.for_asset_class(acmap.get(s, "equity")).round_trip_bps / 1e4
                     for s in universe])
    w = np.zeros(len(universe))
    eq = [init_cap]
    out_dates = [dts[start]]
    for t in range(start, L - 1):
        reb_cost = 0.0
        if (t - start) % step == 0:                       # rebalancement
            win = rets[:, max(0, t - lookback):t]
            if win.shape[1] >= 20:
                cov = _cov_annual(win)
                nw = np.asarray(equal_risk_contribution(cov), float)
                last2 = A[:, t] / A[:, t - 2] - 1
                nw_bl = np.where(np.abs(last2) > blackout_move, 0.0, nw)
                if int((nw_bl > 0).sum()) >= min_names:
                    nw = nw_bl
                s1 = nw.sum(); nw = nw / s1 if s1 > 0 else nw
                nw = _cap_weights(nw, max_weight)
                pv = float(np.sqrt(max(0.0, nw @ cov @ nw)))
                gross = 0.0 if pv <= 0 else min(1.0, tgt_vol / pv)
                nw = nw * gross
                if band > 0 and w.sum() > 0:
                    nw = np.where(np.abs(nw - w) < band, w, nw)
                reb_cost = float((np.abs(nw - w) * rt).sum())   # #P0-3 : coût du turnover ce jour-là
                w = nw
        r_d = float((w * (A[:, t + 1] / A[:, t] - 1)).sum()) - reb_cost   # rendement quotidien NET de coûts
        eq.append(eq[-1] * (1 + r_d))
        out_dates.append(dts[t + 1])
    if len(eq) < 30:
        return {"available": False}
    return {"available": True, "equity": [round(x, 2) for x in eq], "dates": out_dates}


def _weights_at(A, rets, t, lookback, blackout_move, max_weight, min_names, tgt_vol):
    """Poids du preset au temps t (ERC + blackout diversifié + plafond + DD-target)."""
    win = rets[:, max(0, t - lookback):t]
    if win.shape[1] < 20:
        return None
    cov = _cov_annual(win)
    w = np.asarray(equal_risk_contribution(cov), float)
    last2 = A[:, t] / A[:, t - 2] - 1
    w_bl = np.where(np.abs(last2) > blackout_move, 0.0, w)
    if int((w_bl > 0).sum()) >= min_names:
        w = w_bl
    s1 = w.sum(); w = w / s1 if s1 > 0 else w
    w = _cap_weights(w, max_weight)
    pv = float(np.sqrt(max(0.0, w @ cov @ w)))
    gross = 0.0 if pv <= 0 else min(1.0, tgt_vol / pv)
    return w * gross


def preset_trade_log(data: dict, quality: dict | None = None, asset_classes: dict | None = None,
                     dd_target: float = 0.35, band: float = 0.03, step: int = 21, lookback: int = 120,
                     top_k: int = 30, k_dd: float = 1.6, blackout_move: float = 0.12,
                     max_weight: float = 0.10, min_names: int = 12, init_cap: float = 10000.0,
                     max_trades: int = 150) -> dict:
    """Journal des TRADES du preset : à chaque rebalancement, variations de poids → achats/ventes
    (date, symbole, sens, poids avant/après, notionnel ≈ Δpoids × capital). Net du turnover."""
    syms = [s for s, b in data.items() if b and len(b) > lookback + step]
    if len(syms) < 5:
        return {"available": False}
    L = min(len(data[s]) for s in syms)
    M = {s: np.asarray([b.close for b in data[s]][-L:], float) for s in syms}
    quality = quality or {}  # conservé pour compat API ; PLUS utilisé pour l'univers (anti-fuite, cf. _price_universe)
    universe = _price_universe(data, syms, lookback, top_k)
    # même logique « courbe la plus longue » que preset_equity_daily (min_names plus longs historiques)
    _lens = sorted((len(data[s]) for s in universe), reverse=True)
    _need = _lens[min(min_names, len(_lens)) - 1] if _lens else 0
    universe = [s for s in universe if len(data[s]) >= _need] or universe
    L = min(len(data[s]) for s in universe)
    M = {s: np.asarray([b.close for b in data[s]][-L:], float) for s in universe}
    # dates PAR SYMBOLE (chacun aligné sur SES propres barres) → un marqueur tombe toujours dans la
    # fenêtre du titre (sinon le signal d'entrée précède le début des données du titre = invisible).
    D = {s: [b.ts.isoformat()[:10] for b in data[s]][-L:] for s in universe}
    A = np.asarray([M[s] for s in universe])
    rets = A[:, 1:] / A[:, :-1] - 1
    tgt_vol = max(0.0, abs(dd_target)) / k_dd
    start = max(lookback, 50)
    prev = np.zeros(len(universe))
    trades, turn, rebs = [], 0.0, 0
    for t in range(start, L - 1, step):
        w = _weights_at(A, rets, t, lookback, blackout_move, max_weight, min_names, tgt_vol)
        if w is None:
            continue
        if band > 0 and prev.sum() > 0:
            w = np.where(np.abs(w - prev) < band, prev, w)
        rebs += 1
        turn += float(np.abs(w - prev).sum())
        for i, sym in enumerate(universe):
            d = float(w[i] - prev[i])
            if abs(d) > 0.005:                      # variation matérielle (>0.5 %)
                if prev[i] <= 1e-4:
                    reason = "entrée (univers qualité, risk-parity)"
                elif w[i] <= 1e-4:
                    reason = "sortie (hors univers / blackout)"
                else:
                    reason = "renforcement (risk-parity)" if d > 0 else "allègement (DD-target/risk-parity)"
                trades.append({"date": D[sym][t], "symbol": sym,
                               "side": "BUY" if d > 0 else "SELL",
                               "from": round(float(prev[i]), 4), "to": round(float(w[i]), 4),
                               "notional": round(abs(d) * init_cap, 2), "reason": reason})
        prev = w
    if not trades:
        return {"available": False}
    trades = sorted(trades, key=lambda x: x["date"], reverse=True)[:max_trades]
    per_year = 252.0 / step
    return {"available": True, "trades": trades, "n_rebalances": rebs,
            "turnover_annual": round(turn / rebs * per_year, 2) if rebs else 0.0}


def preset_ledger(data: dict, quality: dict | None = None, asset_classes: dict | None = None,
                  dd_target: float = 0.35, band: float = 0.03, step: int = 21, lookback: int = 120,
                  top_k: int = 30, k_dd: float = 1.6, blackout_move: float = 0.12,
                  max_weight: float = 0.10, min_names: int = 12, init_cap: float = 10000.0,
                  max_trades: int = 500, core_closes: list | None = None, core_pct: float = 0.0,
                  core_sym: str = "QQQ") -> dict:
    """Journal de trades RÉEL du portefeuille de production (backtest discret parts/cash sur prix
    réels) qui JUSTIFIE la performance affichée : chaque achat/vente avec date, actif, sens, qté,
    prix, PRU (coût moyen), P&L réalisé ($ et %), motif. Inclut le CŒUR indiciel (core_sym à
    core_pct) + le satellite preset à (1-core_pct). Equity finale = cash + positions → réconcilie
    la courbe du dashboard. PRU = coût moyen pondéré."""
    syms = [s for s, b in data.items() if b and len(b) > lookback + step]
    if len(syms) < 5:
        return {"available": False}
    # COÛTS RÉELS : commission + slippage déduits du cash à CHAQUE exécution, calibrés sur les barèmes
    # courtiers (actions→Alpaca 0 % ; crypto→BitMart 0,25 % ; IBKR minimum 1 $/ordre…).
    # Désactivable via QUANT_FEES=0.
    from packages.execution.costs import broker_fee
    acmap = asset_classes or {}
    _fees_on = os.environ.get("QUANT_FEES", "1") != "0"

    def _tc(sym: str, notional: float, side: str = "BUY") -> float:   # coût RÉEL de l'exécution ($)
        return broker_fee(acmap.get(sym, "equity"), notional, side) if _fees_on else 0.0

    fees_paid = 0.0
    quality = quality or {}  # conservé pour compat API ; PLUS utilisé pour l'univers (anti-fuite, cf. _price_universe)
    universe = _price_universe(data, syms, lookback, top_k)
    _lens = sorted((len(data[s]) for s in universe), reverse=True)
    _need = _lens[min(min_names, len(_lens)) - 1] if _lens else 0
    universe = [s for s in universe if len(data[s]) >= _need] or universe
    L = min(len(data[s]) for s in universe)
    M = {s: np.asarray([b.close for b in data[s]][-L:], float) for s in universe}
    ref = max(universe, key=lambda s: len(data[s]))
    dts = [b.ts.isoformat()[:10] for b in data[ref]][-L:]
    A = np.asarray([M[s] for s in universe])
    rets = A[:, 1:] / A[:, :-1] - 1
    idx = {s: i for i, s in enumerate(universe)}
    tgt_vol = max(0.0, abs(dd_target)) / k_dd
    start = max(lookback, 50)
    cash = float(init_cap)
    shares = {s: 0.0 for s in universe}
    cost = {s: 0.0 for s in universe}                     # PRU (coût moyen pondéré)
    w = np.zeros(len(universe))
    trades: list[dict] = []
    realized = 0.0
    # CŒUR indiciel (ex. QQQ à 50 %) inclus comme une ligne, aligné sur la fenêtre du preset.
    # Robuste : si le cœur est un peu plus court, on cale sa queue et on remplit le début à plat
    # (le cœur ne contribue qu'à partir de sa 1re donnée) → le % cœur agit dès que possible.
    _cp = max(0.0, min(1.0, float(core_pct)))
    core_on = bool(core_closes) and _cp > 0 and len(core_closes) >= 250
    if core_on:
        _cc = list(core_closes)
        core_arr = (np.asarray(_cc[-L:], float) if len(_cc) >= L
                    else np.asarray([_cc[0]] * (L - len(_cc)) + _cc, float))
    else:
        core_arr = None
    qsh = qcost = 0.0
    sat = 1.0 - _cp if core_on else 1.0                   # part allouée au satellite preset
    eq_curve = [float(init_cap)]                           # courbe d'equity QUOTIDIENNE (parts tenues)
    out_dates = [dts[start]]
    for t in range(start, L - 1):
        if (t - start) % step == 0:                        # rééquilibrage (entre deux, on TIENT les parts)
            nw = _weights_at(A, rets, t, lookback, blackout_move, max_weight, min_names, tgt_vol)
            if nw is not None:
                if band > 0 and w.sum() > 0:
                    nw = np.where(np.abs(nw - w) < band, w, nw)
                px = A[:, t]
                equity = cash + sum(shares[s] * px[idx[s]] for s in universe) + (qsh * float(core_arr[t]) if core_on else 0.0)
                if core_on:                                # rééquilibrage du CŒUR (QQQ) à core_pct
                    cpx = float(core_arr[t]); d_val = float(_cp * equity - qsh * cpx)
                    if cpx > 0 and abs(d_val) >= max(0.004 * equity, 1.0):
                        if d_val > 0:
                            dq = d_val / cpx; tot = qsh + dq
                            qcost = (qcost * qsh + cpx * dq) / tot if tot > 0 else cpx
                            _fee = _tc(core_sym, d_val); fees_paid += _fee
                            qsh, cash = tot, cash - d_val - _fee
                            trades.append({"date": dts[t], "symbol": core_sym, "side": "BUY", "qty": round(dq, 4),
                                           "price": round(cpx, 2), "notional": round(d_val, 2), "avg_cost": round(qcost, 2),
                                           "pnl": None, "pnl_pct": None, "fee": round(_fee, 2), "reason": "cœur indiciel (rééquilibrage)"})
                        else:
                            sq = min(qsh, -d_val / cpx)
                            if sq > 1e-9:
                                _fee = _tc(core_sym, sq * cpx, "SELL"); fees_paid += _fee
                                pnl = (cpx - qcost) * sq; realized += pnl; qsh, cash = qsh - sq, cash + sq * cpx - _fee
                                trades.append({"date": dts[t], "symbol": core_sym, "side": "SELL", "qty": round(sq, 4),
                                               "price": round(cpx, 2), "notional": round(sq * cpx, 2), "avg_cost": round(qcost, 2),
                                               "pnl": round(pnl, 2), "pnl_pct": round(cpx / qcost - 1, 4) if qcost > 0 else None,
                                               "fee": round(_fee, 2), "reason": "cœur indiciel (allègement)"})
                for i, s in enumerate(universe):
                    price = float(px[i])
                    if price <= 0:
                        continue
                    d_val = float(nw[i] * sat * equity - shares[s] * price)   # satellite = (1-core_pct)
                    if abs(d_val) < max(0.004 * equity, 1.0):     # variation négligeable → pas de trade
                        continue
                    if d_val > 0:                                  # ACHAT
                        dq = d_val / price
                        tot = shares[s] + dq
                        cost[s] = (cost[s] * shares[s] + price * dq) / tot if tot > 0 else price
                        _fee = _tc(s, d_val); fees_paid += _fee
                        shares[s], cash = tot, cash - d_val - _fee
                        reason = "entrée (univers qualité, risk-parity)" if (shares[s] - dq) <= 1e-9 else "renforcement (risk-parity)"
                        trades.append({"date": dts[t], "symbol": s, "side": "BUY", "qty": round(dq, 4),
                                       "price": round(price, 2), "notional": round(d_val, 2),
                                       "avg_cost": round(cost[s], 2), "pnl": None, "pnl_pct": None,
                                       "fee": round(_fee, 2), "reason": reason})
                    else:                                          # VENTE (P&L réalisé vs PRU)
                        sq = min(shares[s], -d_val / price)
                        if sq <= 1e-9:
                            continue
                        pnl = (price - cost[s]) * sq
                        realized += pnl
                        _fee = _tc(s, sq * price, "SELL"); fees_paid += _fee
                        shares[s], cash = shares[s] - sq, cash + sq * price - _fee
                        reason = ("sortie (hors univers / blackout)" if (nw[i] <= 1e-4 or shares[s] <= 1e-6)
                                  else "allègement (DD-target/risk-parity)")
                        trades.append({"date": dts[t], "symbol": s, "side": "SELL", "qty": round(sq, 4),
                                       "price": round(price, 2), "notional": round(sq * price, 2),
                                       "avg_cost": round(cost[s], 2), "pnl": round(pnl, 2),
                                       "pnl_pct": round(price / cost[s] - 1, 4) if cost[s] > 0 else None,
                                       "fee": round(_fee, 2), "reason": reason})
                w = nw
        px1 = A[:, t + 1]                                  # valorisation quotidienne (mark-to-market)
        val = sum(shares[s] * px1[idx[s]] for s in universe) + (qsh * float(core_arr[t + 1]) if core_on else 0.0)
        eq_curve.append(cash + val)
        out_dates.append(dts[t + 1])
    pxf = A[:, L - 1]
    open_pos = [{"symbol": s, "qty": round(shares[s], 4), "avg_cost": round(cost[s], 2),
                 "price": round(float(pxf[idx[s]]), 2), "value": round(shares[s] * float(pxf[idx[s]]), 2),
                 "pnl": round((float(pxf[idx[s]]) - cost[s]) * shares[s], 2),
                 "pnl_pct": round(float(pxf[idx[s]]) / cost[s] - 1, 4) if cost[s] > 0 else None}
                for s in universe if shares[s] > 1e-6]
    if core_on and qsh > 1e-9:                            # ligne du cœur indiciel (QQQ)
        _cpx = float(core_arr[L - 1])
        open_pos.insert(0, {"symbol": core_sym, "qty": round(qsh, 4), "avg_cost": round(qcost, 2),
                            "price": round(_cpx, 2), "value": round(qsh * _cpx, 2),
                            "pnl": round((_cpx - qcost) * qsh, 2),
                            "pnl_pct": round(_cpx / qcost - 1, 4) if qcost > 0 else None})
    final_eq = cash + sum(p["value"] for p in open_pos)
    unrealized = sum(p["pnl"] for p in open_pos)
    n_all = len(trades)
    # --- P&L LATENT par ACHAT, RÉCONCILIÉ avec les positions ouvertes ---
    # Un achat ne porte du latent que pour les parts ENCORE détenues : on suit en FIFO les parts
    # consommées par les ventes ; les parts survivantes sont valorisées au PRU MOYEN de la position.
    # Ainsi Σ(latent des achats) = Σ(latent des positions ouvertes) à l'$ près, et
    # Σ(P&L réalisé des ventes) + Σ(latent des achats) = (equity finale − capital initial) + frais.
    from collections import deque as _deque
    _cur = {s: float(pxf[idx[s]]) for s in universe}
    _avgc = {s: cost[s] for s in universe}
    if core_on:
        _cur[core_sym] = float(core_arr[L - 1]); _avgc[core_sym] = qcost
    _lots: dict = {}
    for _t in trades:                                      # ordre chronologique (ascendant)
        s = _t["symbol"]; q = _t.get("qty") or 0.0
        if _t["side"] == "BUY":
            _t["_rem"] = q; _t["latent"], _t["latent_pct"] = 0.0, None
            _lots.setdefault(s, _deque()).append(_t)
        else:                                              # VENTE : consomme les achats au FIFO
            _t["latent"], _t["latent_pct"] = None, None
            dq = q; dl = _lots.get(s)
            while dq > 1e-9 and dl:
                lot = dl[0]; take = min(lot["_rem"], dq); lot["_rem"] -= take; dq -= take
                if lot["_rem"] <= 1e-9:
                    dl.popleft()
    for s, dl in _lots.items():                            # parts survivantes → latent au PRU moyen
        cp, ac = _cur.get(s), _avgc.get(s, 0.0)
        for lot in dl:
            rem = lot.get("_rem", 0.0)
            if rem > 1e-9 and cp and ac > 0:
                lot["latent"] = round((cp - ac) * rem, 2)
                lot["latent_pct"] = round(cp / ac - 1, 4)
    for _t in trades:
        _t.pop("_rem", None)
    trades = sorted(trades, key=lambda x: x["date"], reverse=True)[:max_trades]
    # transparence frais : courtiers retenus + estimation de la perf SANS frais (premier ordre).
    from packages.execution.costs import broker_for
    _gross_eq = final_eq + fees_paid                       # ≈ equity sans frais (estimation au 1er ordre)
    _brokers = {}
    if _fees_on:
        _acs = {acmap.get(s, "equity") for s in universe} | {acmap.get(core_sym, "equity") if core_on else "equity"}
        _brokers = {ac: broker_for(ac) for ac in sorted(_acs)}
    return {"available": True, "trades": trades, "open_positions": open_pos,
            "equity": [round(x, 2) for x in eq_curve], "dates": out_dates,
            "summary": {"init_cap": round(init_cap, 2), "final_equity": round(final_eq, 2),
                        "total_return": round(final_eq / init_cap - 1, 4),
                        "realized_pnl": round(realized, 2), "unrealized_pnl": round(unrealized, 2),
                        "cash": round(cash, 2), "n_trades": n_all,
                        "fees_paid": round(fees_paid, 2), "fees_pct": round(fees_paid / init_cap, 4),
                        "gross_return": round(_gross_eq / init_cap - 1, 4), "fees_on": _fees_on,
                        "brokers": _brokers,
                        # réconciliation explicite : P&L total = réalisé + latent = gain du graphe + frais
                        "total_pnl": round(realized + unrealized, 2),
                        "graph_gain": round(final_eq - init_cap, 2),
                        "reconciles": abs((realized + unrealized) - (final_eq - init_cap) - fees_paid) < max(1.0, 0.001 * init_cap),
                        "start": dts[start], "end": dts[L - 1]}}
