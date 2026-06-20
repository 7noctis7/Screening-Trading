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
    syms = [s for s, b in data.items() if b and len(b) > lookback + step]
    if len(syms) < 5:
        return {"available": False}
    quality = quality or {}
    q = {s: quality.get(s) for s in syms if quality.get(s) is not None}
    universe = (sorted(q, key=lambda s: q[s], reverse=True)[:top_k] if len(q) >= 5 else syms[:top_k])
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
    quality = quality or {}
    q = {s: quality.get(s) for s in syms if quality.get(s) is not None}
    universe = (sorted(q, key=lambda s: q[s], reverse=True)[:top_k] if len(q) >= 5 else syms[:top_k])
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
                  top_k: int = 30, k_dd: float = 2.5, blackout_move: float = 0.12,
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
    quality = quality or {}
    q = {s: quality.get(s) for s in syms if quality.get(s) is not None}
    universe = (sorted(q, key=lambda s: q[s], reverse=True)[:top_k] if len(q) >= 5 else syms[:top_k])
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
                            qsh, cash = tot, cash - d_val
                            trades.append({"date": dts[t], "symbol": core_sym, "side": "BUY", "qty": round(dq, 4),
                                           "price": round(cpx, 2), "notional": round(d_val, 2), "avg_cost": round(qcost, 2),
                                           "pnl": None, "pnl_pct": None, "reason": "cœur indiciel (rééquilibrage)"})
                        else:
                            sq = min(qsh, -d_val / cpx)
                            if sq > 1e-9:
                                pnl = (cpx - qcost) * sq; realized += pnl; qsh, cash = qsh - sq, cash + sq * cpx
                                trades.append({"date": dts[t], "symbol": core_sym, "side": "SELL", "qty": round(sq, 4),
                                               "price": round(cpx, 2), "notional": round(sq * cpx, 2), "avg_cost": round(qcost, 2),
                                               "pnl": round(pnl, 2), "pnl_pct": round(cpx / qcost - 1, 4) if qcost > 0 else None,
                                               "reason": "cœur indiciel (allègement)"})
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
                        shares[s], cash = tot, cash - d_val
                        reason = "entrée (univers qualité, risk-parity)" if (shares[s] - dq) <= 1e-9 else "renforcement (risk-parity)"
                        trades.append({"date": dts[t], "symbol": s, "side": "BUY", "qty": round(dq, 4),
                                       "price": round(price, 2), "notional": round(d_val, 2),
                                       "avg_cost": round(cost[s], 2), "pnl": None, "pnl_pct": None, "reason": reason})
                    else:                                          # VENTE (P&L réalisé vs PRU)
                        sq = min(shares[s], -d_val / price)
                        if sq <= 1e-9:
                            continue
                        pnl = (price - cost[s]) * sq
                        realized += pnl
                        shares[s], cash = shares[s] - sq, cash + sq * price
                        reason = ("sortie (hors univers / blackout)" if (nw[i] <= 1e-4 or shares[s] <= 1e-6)
                                  else "allègement (DD-target/risk-parity)")
                        trades.append({"date": dts[t], "symbol": s, "side": "SELL", "qty": round(sq, 4),
                                       "price": round(price, 2), "notional": round(sq * price, 2),
                                       "avg_cost": round(cost[s], 2), "pnl": round(pnl, 2),
                                       "pnl_pct": round(price / cost[s] - 1, 4) if cost[s] > 0 else None, "reason": reason})
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
    trades = sorted(trades, key=lambda x: x["date"], reverse=True)[:max_trades]
    # P&L LATENT par achat : valeur mark-to-market au DERNIER prix (si tu avais gardé ces parts).
    _last_px = {universe[i]: float(pxf[i]) for i in range(len(universe))}
    if core_on:
        _last_px[core_sym] = float(core_arr[L - 1])
    for _t in trades:
        _lp = _last_px.get(_t["symbol"])
        if _t["side"] == "BUY" and _lp and _t.get("price"):
            _t["latent"] = round((_lp - _t["price"]) * _t["qty"], 2)
            _t["latent_pct"] = round(_lp / _t["price"] - 1, 4)
        else:
            _t["latent"], _t["latent_pct"] = None, None
    return {"available": True, "trades": trades, "open_positions": open_pos,
            "equity": [round(x, 2) for x in eq_curve], "dates": out_dates,
            "summary": {"init_cap": round(init_cap, 2), "final_equity": round(final_eq, 2),
                        "total_return": round(final_eq / init_cap - 1, 4),
                        "realized_pnl": round(realized, 2), "unrealized_pnl": round(unrealized, 2),
                        "cash": round(cash, 2), "n_trades": n_all,
                        "start": dts[start], "end": dts[L - 1]}}
