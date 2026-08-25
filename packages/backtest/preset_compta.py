"""Ledger : backtest discret parts/cash sur prix réels, avec P&L réalisé et latent réconciliés.

Extrait de `preset_backtest.py` le 25/08 (règle < 400 lignes/fichier). Comportement
repris à l'identique — l'ordre des écritures et les seuils sont inchangés.
"""

from __future__ import annotations

import numpy as np

from packages.backtest.preset_curves import _grille, _jours
from packages.backtest.preset_livre import Livre
from packages.backtest.preset_weights import _weights_at


def _serie_coeur(core_closes: list | None, core_pct: float, L: int):
    """CŒUR indiciel (ex. QQQ à 50 %) aligné sur la fenêtre du preset.

    Robuste : si le cœur est un peu plus court, on cale sa queue et on remplit le début à plat
    (le cœur ne contribue qu'à partir de sa 1re donnée) → le % cœur agit dès que possible.
    """
    cp = max(0.0, min(1.0, float(core_pct)))
    if not (bool(core_closes) and cp > 0 and len(core_closes) >= 250):
        return None, cp
    cc = list(core_closes)
    arr = (np.asarray(cc[-L:], float) if len(cc) >= L
           else np.asarray([cc[0]] * (L - len(cc)) + cc, float))
    return arr, cp


def _latent_fifo(trades: list, cur: dict, avgc: dict) -> None:
    """P&L LATENT par ACHAT, RÉCONCILIÉ avec les positions ouvertes (mutation en place).

    Un achat ne porte du latent que pour les parts ENCORE détenues : on suit en FIFO les parts
    consommées par les ventes ; les parts survivantes sont valorisées au PRU MOYEN de la position.
    Ainsi Σ(latent des achats) = Σ(latent des positions ouvertes) à l'$ près, et
    Σ(P&L réalisé des ventes) + Σ(latent des achats) = (equity finale − capital initial) + frais.
    """
    from collections import deque
    lots: dict = {}
    for t in trades:                                   # ordre chronologique (ascendant)
        s, q = t["symbol"], t.get("qty") or 0.0
        if t["side"] == "BUY":
            t["_rem"], t["latent"], t["latent_pct"] = q, 0.0, None
            lots.setdefault(s, deque()).append(t)
        else:                                          # VENTE : consomme les achats au FIFO
            t["latent"], t["latent_pct"] = None, None
            dq, dl = q, lots.get(s)
            while dq > 1e-9 and dl:
                lot = dl[0]
                take = min(lot["_rem"], dq)
                lot["_rem"] -= take
                dq -= take
                if lot["_rem"] <= 1e-9:
                    dl.popleft()
    for s, dl in lots.items():                         # parts survivantes → latent au PRU moyen
        cp, ac = cur.get(s), avgc.get(s, 0.0)
        for lot in dl:
            rem = lot.get("_rem", 0.0)
            if rem > 1e-9 and cp and ac > 0:
                lot["latent"] = round((cp - ac) * rem, 2)
                lot["latent_pct"] = round(cp / ac - 1, 4)
    for t in trades:
        t.pop("_rem", None)


def _positions_ouvertes(livre: Livre, universe: list, pxf, idx: dict, dts: list,
                        L: int, start: int, core_sym: str, core_arr) -> list:
    """Lignes encore détenues. `depuis` : sans la date d'ouverture, un P&L modèle de +158 %
    (dix ans) s'affiche à côté d'un P&L courtier de −1,1 % (trois semaines) comme s'ils étaient
    comparables. Ils ne le sont pas."""
    pos = [{"symbol": s, "qty": round(livre.shares[s], 4), "avg_cost": round(livre.cost[s], 2),
            "price": round(float(pxf[idx[s]]), 2),
            "value": round(livre.shares[s] * float(pxf[idx[s]]), 2),
            "pnl": round((float(pxf[idx[s]]) - livre.cost[s]) * livre.shares[s], 2),
            "depuis": livre.ouvert_depuis.get(s),
            "jours": _jours(livre.ouvert_depuis.get(s), dts[L - 1]),
            "pnl_pct": round(float(pxf[idx[s]]) / livre.cost[s] - 1, 4)
            if livre.cost[s] > 0 else None}
           for s in universe if livre.shares[s] > 1e-6]
    if core_arr is not None and livre.qsh > 1e-9:      # ligne du cœur indiciel (QQQ)
        cpx = float(core_arr[L - 1])
        pos.insert(0, {"symbol": core_sym, "qty": round(livre.qsh, 4),
                       "avg_cost": round(livre.qcost, 2), "price": round(cpx, 2),
                       "value": round(livre.qsh * cpx, 2),
                       "pnl": round((cpx - livre.qcost) * livre.qsh, 2),
                       "depuis": dts[start], "jours": _jours(dts[start], dts[L - 1]),
                       "pnl_pct": round(cpx / livre.qcost - 1, 4) if livre.qcost > 0 else None})
    return pos


def _resume(livre: Livre, open_pos: list, init_cap: float, n_all: int,
            universe: list, core_sym: str, core_on: bool, dts: list,
            L: int, start: int) -> dict:
    """Bloc `summary` : réconciliation explicite P&L total = réalisé + latent = gain + frais."""
    from packages.execution.costs import broker_for
    final_eq = livre.cash + sum(p["value"] for p in open_pos)
    unrealized = sum(p["pnl"] for p in open_pos)
    gross_eq = final_eq + livre.fees_paid      # ≈ equity sans frais (estimation au 1er ordre)
    brokers = {}
    if livre.fees_on:
        acs = ({livre.acmap.get(s, "equity") for s in universe}
               | {livre.acmap.get(core_sym, "equity") if core_on else "equity"})
        brokers = {ac: broker_for(ac) for ac in sorted(acs)}
    total = livre.realized + unrealized
    return {"init_cap": round(init_cap, 2), "final_equity": round(final_eq, 2),
            "total_return": round(final_eq / init_cap - 1, 4),
            "realized_pnl": round(livre.realized, 2), "unrealized_pnl": round(unrealized, 2),
            "cash": round(livre.cash, 2), "n_trades": n_all,
            "fees_paid": round(livre.fees_paid, 2),
            "fees_pct": round(livre.fees_paid / init_cap, 4),
            "gross_return": round(gross_eq / init_cap - 1, 4), "fees_on": livre.fees_on,
            "brokers": brokers, "total_pnl": round(total, 2),
            "graph_gain": round(final_eq - init_cap, 2),
            "reconciles": abs(total - (final_eq - init_cap) - livre.fees_paid)
            < max(1.0, 0.001 * init_cap),
            "start": dts[start], "end": dts[L - 1]}


def _derouler(livre: Livre, A, rets, universe: list, idx: dict, dts: list, L: int,
              start: int, step: int, band: float, lookback: int, blackout_move: float,
              max_weight: float, min_names: int, tgt_vol: float, core_arr, cp: float,
              core_sym: str, init_cap: float) -> tuple[list, list]:
    """Déroule le backtest jour par jour : rééquilibrage tous les `step`, mark-to-market sinon."""
    core_on = core_arr is not None
    sat = 1.0 - cp if core_on else 1.0        # part allouée au satellite preset
    w = np.zeros(len(universe))
    eq_curve, out_dates = [float(init_cap)], [dts[start]]
    for t in range(start, L - 1):
        if (t - start) % step == 0:           # rééquilibrage (entre deux, on TIENT les parts)
            nw = _weights_at(A, rets, t, lookback, blackout_move, max_weight,
                             min_names, tgt_vol)
            if nw is not None:
                if band > 0 and w.sum() > 0:
                    nw = np.where(np.abs(nw - w) < band, w, nw)
                px = A[:, t]
                cpx = float(core_arr[t]) if core_on else None
                equity = livre.equity(px, idx, universe, cpx)
                if core_on:
                    livre.rebalance_coeur(core_sym, dts[t], cpx, cp * equity, equity)
                livre.rebalance_satellite(universe, dts[t], px, nw, sat, equity)
                w = nw
        px1 = A[:, t + 1]                     # valorisation quotidienne (mark-to-market)
        val = sum(livre.shares[s] * px1[idx[s]] for s in universe)
        eq_curve.append(livre.cash + val
                        + (livre.qsh * float(core_arr[t + 1]) if core_on else 0.0))
        out_dates.append(dts[t + 1])
    return eq_curve, out_dates


def preset_ledger(data: dict, quality: dict | None = None, asset_classes: dict | None = None,
                  dd_target: float = 0.35, band: float = 0.03, step: int = 21,
                  lookback: int = 120, top_k: int = 30, k_dd: float = 1.6,
                  blackout_move: float = 0.12, max_weight: float = 0.10, min_names: int = 12,
                  init_cap: float = 10000.0, max_trades: int = 500,
                  core_closes: list | None = None, core_pct: float = 0.0,
                  core_sym: str = "QQQ") -> dict:
    """Journal de trades RÉEL du portefeuille de production (backtest discret parts/cash sur prix
    réels) qui JUSTIFIE la performance affichée : chaque achat/vente avec date, actif, sens, qté,
    prix, PRU (coût moyen), P&L réalisé ($ et %), motif. Inclut le CŒUR indiciel (core_sym à
    core_pct) + le satellite preset à (1-core_pct). Equity finale = cash + positions → réconcilie
    la courbe du dashboard. PRU = coût moyen pondéré."""
    _ = quality  # conservé pour compat API ; PLUS utilisé pour l'univers (anti-fuite)
    g = _grille(data, lookback, step, top_k, min_names)
    if g is None:
        return {"available": False}
    universe, dts, A = g
    L = A.shape[1]
    rets = A[:, 1:] / A[:, :-1] - 1
    idx = {s: i for i, s in enumerate(universe)}
    tgt_vol = max(0.0, abs(dd_target)) / k_dd
    start = max(lookback, 50)
    livre = Livre(init_cap, universe, asset_classes or {})
    core_arr, cp = _serie_coeur(core_closes, core_pct, L)
    core_on = core_arr is not None
    eq_curve, out_dates = _derouler(livre, A, rets, universe, idx, dts, L, start, step,
                                    band, lookback, blackout_move, max_weight, min_names,
                                    tgt_vol, core_arr, cp, core_sym, init_cap)
    pxf = A[:, L - 1]
    open_pos = _positions_ouvertes(livre, universe, pxf, idx, dts, L, start,
                                   core_sym, core_arr)
    n_all = len(livre.trades)
    cur = {s: float(pxf[idx[s]]) for s in universe}
    avgc = dict(livre.cost)
    if core_on:
        cur[core_sym] = float(core_arr[L - 1])
        avgc[core_sym] = livre.qcost
    _latent_fifo(livre.trades, cur, avgc)
    trades = sorted(livre.trades, key=lambda x: x["date"], reverse=True)[:max_trades]
    return {"available": True, "trades": trades, "open_positions": open_pos,
            "equity": [round(x, 2) for x in eq_curve], "dates": out_dates,
            "summary": _resume(livre, open_pos, init_cap, n_all, universe, core_sym,
                               core_on, dts, L, start)}
