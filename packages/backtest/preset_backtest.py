"""Backtest du PRESET stratégique « best practice » (point-in-time, anti-fuite).

Combine, à chaque rebalancement :
  1. **Tilt qualité** : univers = top-K par score fondamental (statique → neutre vis-à-vis des prix,
     pas de fuite ; c'est un *sleeve* facteur qualité).
  2. **Risk-parity (ERC)** : chaque actif contribue également au risque (covariance trailing).
  3. **DD-target exposure** : exposition brute dimensionnée pour viser un drawdown cible
     (vol-cible ≈ DD/2.5), le reste en cash → pilotage par la volatilité réalisée.
  4. **Earnings blackout (proxy)** : on évite d'entrer juste après un choc binaire (|move 2 j| élevé).
  5. **No-trade band** : on ne bouge un poids que s'il dérive de plus de `band` (turnover ↓).
  6. **Coûts par classe d'actifs** déduits du turnover (réalisme).

Compare le preset à l'équipondéré (bench) et, si fourni, à la courbe du swing. numpy pur, testable.
"""

from __future__ import annotations

import numpy as np

from packages.backtest.conviction_backtest import _stats
from packages.execution.costs import CostModel
from packages.portfolio.optimize import equal_risk_contribution


def _cov_annual(win: np.ndarray) -> np.ndarray:
    if win.shape[0] == 1:
        return np.array([[float(win.var()) * 252]])
    return np.cov(win) * 252


def preset_backtest(data: dict, quality: dict | None = None, asset_classes: dict | None = None,
                    swing_equity: list | None = None, dd_target: float = 0.25, band: float = 0.03,
                    step: int = 21, lookback: int = 120, top_k: int = 30, k_dd: float = 2.5,
                    blackout_move: float = 0.12) -> dict:
    syms = [s for s, b in data.items() if b and len(b) > lookback + 2 * step]
    if len(syms) < 5:
        return {"available": False}
    L = min(len(data[s]) for s in syms)
    M = {s: np.asarray([b.close for b in data[s]][-L:], float) for s in syms}
    acmap = asset_classes or {}
    quality = quality or {}

    # univers tilt-qualité (statique → factor sleeve, sans fuite des prix)
    q = {s: quality.get(s) for s in syms if quality.get(s) is not None}
    universe = (sorted(q, key=lambda s: q[s], reverse=True)[:top_k]
                if len(q) >= 5 else syms[:top_k])
    A = np.asarray([M[s] for s in universe])                    # n × L
    rets = A[:, 1:] / A[:, :-1] - 1
    tgt_vol = max(0.0, abs(dd_target)) / k_dd
    rt = np.asarray([CostModel.for_asset_class(acmap.get(s, "equity")).round_trip_bps / 1e4
                     for s in universe])

    prev_w = np.zeros(len(universe))
    port: list[float] = []
    gross_hist: list[float] = []
    turn = 0.0
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
        pv = float(np.sqrt(max(0.0, w @ cov @ w)))              # DD-target : exposition pilotée par la vol
        gross = 0.0 if pv <= 0 else min(1.0, tgt_vol / pv)
        w = w * gross
        if band > 0 and prev_w.sum() > 0:                       # bande de non-trading
            w = np.where(np.abs(w - prev_w) < band, prev_w, w)
        nxt = min(t + step, L - 1)
        fwd = A[:, nxt] / A[:, t] - 1                           # rendement RÉALISÉ après t
        cost = float((np.abs(w - prev_w) * rt).sum())
        port.append(float((w * fwd).sum()) - cost)
        turn += float(np.abs(w - prev_w).sum())
        gross_hist.append(float(w.sum()))
        prev_w = w
    if len(port) < 3:
        return {"available": False}

    per_year = 252.0 / step

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
                          top_k: int = 30, k_dd: float = 2.5, blackout_move: float = 0.12,
                          max_weight: float = 0.10, min_names: int = 12) -> dict:
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
    # PLAFOND DE CONCENTRATION : aucune position > max_weight (anti-sur-concentration), itéré
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
    s2 = w.sum()
    w = w / s2 if s2 > 0 else w
    tgt_vol = max(0.0, abs(dd_target)) / k_dd
    pv = float(np.sqrt(max(0.0, w @ cov @ w)))
    gross = 0.0 if pv <= 0 else min(1.0, tgt_vol / pv)
    w = w * gross
    return {universe[i]: round(float(w[i]), 4) for i in range(len(universe)) if w[i] > 1e-4}


def preset_equity_daily(data: dict, quality: dict | None = None, asset_classes: dict | None = None,
                        dd_target: float = 0.35, band: float = 0.03, step: int = 21,
                        lookback: int = 120, top_k: int = 30, k_dd: float = 2.5,
                        blackout_move: float = 0.12, max_weight: float = 0.10, min_names: int = 12,
                        init_cap: float = 10000.0) -> dict:
    """Courbe d'equity QUOTIDIENNE du preset (pour le dashboard) : rebalancement tous les `step`
    jours, accumulation des rendements quotidiens entre deux rebalancements. Renvoie
    {equity:[$], dates:[iso], available}. Même logique que le backtest (anti-fuite)."""
    from packages.backtest.preset_backtest import preset_latest_weights  # noqa: F401 (cohérence)
    syms = [s for s, b in data.items() if b and len(b) > lookback + step]
    if len(syms) < 5:
        return {"available": False}
    L = min(len(data[s]) for s in syms)
    M = {s: np.asarray([b.close for b in data[s]][-L:], float) for s in syms}
    ref = max(syms, key=lambda s: len(data[s]))
    dts = [b.ts.isoformat() for b in data[ref]][-L:]
    quality = quality or {}
    q = {s: quality.get(s) for s in syms if quality.get(s) is not None}
    universe = (sorted(q, key=lambda s: q[s], reverse=True)[:top_k] if len(q) >= 5 else syms[:top_k])
    A = np.asarray([M[s] for s in universe])
    rets = A[:, 1:] / A[:, :-1] - 1
    tgt_vol = max(0.0, abs(dd_target)) / k_dd
    start = max(lookback, 50)
    w = np.zeros(len(universe))
    eq = [init_cap]
    out_dates = [dts[start]]
    for t in range(start, L - 1):
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
                for _ in range(3):
                    over = nw > max_weight
                    if not over.any():
                        break
                    exc = (nw[over] - max_weight).sum(); nw[over] = max_weight
                    free = ~over & (nw > 0)
                    if free.any():
                        nw[free] += exc * nw[free] / nw[free].sum()
                    else:
                        break
                s2 = nw.sum(); nw = nw / s2 if s2 > 0 else nw
                pv = float(np.sqrt(max(0.0, nw @ cov @ nw)))
                gross = 0.0 if pv <= 0 else min(1.0, tgt_vol / pv)
                nw = nw * gross
                if band > 0 and w.sum() > 0:
                    nw = np.where(np.abs(nw - w) < band, w, nw)
                w = nw
        r_d = float((w * (A[:, t + 1] / A[:, t] - 1)).sum())   # rendement quotidien réalisé
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
    for _ in range(3):
        over = w > max_weight
        if not over.any():
            break
        exc = (w[over] - max_weight).sum(); w[over] = max_weight
        free = ~over & (w > 0)
        if free.any():
            w[free] += exc * w[free] / w[free].sum()
        else:
            break
    s2 = w.sum(); w = w / s2 if s2 > 0 else w
    pv = float(np.sqrt(max(0.0, w @ cov @ w)))
    gross = 0.0 if pv <= 0 else min(1.0, tgt_vol / pv)
    return w * gross


def preset_trade_log(data: dict, quality: dict | None = None, asset_classes: dict | None = None,
                     dd_target: float = 0.35, band: float = 0.03, step: int = 21, lookback: int = 120,
                     top_k: int = 30, k_dd: float = 2.5, blackout_move: float = 0.12,
                     max_weight: float = 0.10, min_names: int = 12, init_cap: float = 10000.0,
                     max_trades: int = 150) -> dict:
    """Journal des TRADES du preset : à chaque rebalancement, variations de poids → achats/ventes
    (date, symbole, sens, poids avant/après, notionnel ≈ Δpoids × capital). Net du turnover."""
    syms = [s for s, b in data.items() if b and len(b) > lookback + step]
    if len(syms) < 5:
        return {"available": False}
    L = min(len(data[s]) for s in syms)
    M = {s: np.asarray([b.close for b in data[s]][-L:], float) for s in syms}
    ref = max(syms, key=lambda s: len(data[s]))
    dts = [b.ts.isoformat()[:10] for b in data[ref]][-L:]
    quality = quality or {}
    q = {s: quality.get(s) for s in syms if quality.get(s) is not None}
    universe = (sorted(q, key=lambda s: q[s], reverse=True)[:top_k] if len(q) >= 5 else syms[:top_k])
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
                trades.append({"date": dts[t], "symbol": sym,
                               "side": "BUY" if d > 0 else "SELL",
                               "from": round(float(prev[i]), 4), "to": round(float(w[i]), 4),
                               "notional": round(abs(d) * init_cap, 2)})
        prev = w
    if not trades:
        return {"available": False}
    trades = sorted(trades, key=lambda x: x["date"], reverse=True)[:max_trades]
    per_year = 252.0 / step
    return {"available": True, "trades": trades, "n_rebalances": rebs,
            "turnover_annual": round(turn / rebs * per_year, 2) if rebs else 0.0}
