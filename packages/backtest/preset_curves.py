"""Courbes du dashboard : equity quotidienne et journal de trades (poids).

Extrait de `preset_backtest.py` le 25/08 (règle < 400 lignes/fichier).

Le bloc de calcul des poids de `preset_equity_daily` ré-implémentait mot pour mot
`_weights_at` ; il l'appelle désormais — même arithmétique, une seule source.
"""

from __future__ import annotations

import numpy as np

from packages.backtest.panel import aligner_sans_trous
from packages.backtest.preset_config import _price_universe
from packages.backtest.preset_weights import _weights_at
from packages.execution.costs import CostModel


def _jours(debut: str | None, fin: str | None) -> int | None:
    """Durée de détention en jours calendaires — le dénominateur manquant de tout P&L affiché."""
    if not debut or not fin:
        return None
    try:
        from datetime import date
        d0 = date.fromisoformat(str(debut)[:10])
        d1 = date.fromisoformat(str(fin)[:10])
    except ValueError:
        return None
    return max(0, (d1 - d0).days)


def _grille(data: dict, lookback: int, step: int, top_k: int, min_names: int):
    """Univers ANTI-FUITE + grille alignée par DATE et SANS NaN (cf. panel.aligner_sans_trous).

    Ces fonctions prenaient les dates d'UNE série de référence et supposaient que les autres
    partageaient son calendrier ; avec des actions et des cryptos dans le même panier, cette
    supposition décalait les colonnes de plusieurs années. On refuse ici les NaN plutôt que de
    les gérer : la comptabilité parts/cash en aval produirait un P&L FAUX, pas une erreur visible.
    """
    syms = [s for s, b in data.items() if b and len(b) > lookback + step]
    if len(syms) < 5:
        return None
    universe, dts, A = aligner_sans_trous(data, _price_universe(data, syms, lookback, top_k),
                                          min_names)
    if len(universe) < 2 or A.shape[1] < lookback + step:
        return None
    return universe, dts, A


def _couts_aller_retour(universe: list, asset_classes: dict | None) -> np.ndarray:
    """#P0-3 : barème de coûts par classe d'actifs (fin de l'equity brute)."""
    acmap = asset_classes or {}
    return np.asarray([CostModel.for_asset_class(acmap.get(s, "equity")).round_trip_bps / 1e4
                       for s in universe])


def preset_equity_daily(data: dict, quality: dict | None = None,
                        asset_classes: dict | None = None,
                        dd_target: float = 0.35, band: float = 0.03, step: int = 21,
                        lookback: int = 120, top_k: int = 30, k_dd: float = 1.6,
                        blackout_move: float = 0.12, max_weight: float = 0.10,
                        min_names: int = 12, init_cap: float = 10000.0) -> dict:
    """Courbe d'equity QUOTIDIENNE du preset (pour le dashboard) : rebalancement tous les `step`
    jours, accumulation des rendements quotidiens entre deux rebalancements. Renvoie
    {equity:[$], dates:[iso], available}. Univers ANTI-FUITE (momentum prix-only, cf. _price_universe)
    et rendements quotidiens NETS des coûts de turnover (barème par classe d'actifs)."""
    _ = quality  # conservé pour compat API ; PLUS utilisé pour l'univers (anti-fuite)
    g = _grille(data, lookback, step, top_k, min_names)
    if g is None:
        return {"available": False}
    universe, dts, A = g
    L = A.shape[1]
    rets = A[:, 1:] / A[:, :-1] - 1
    tgt_vol = max(0.0, abs(dd_target)) / k_dd
    start = max(lookback, 50)
    rt = _couts_aller_retour(universe, asset_classes)
    w = np.zeros(len(universe))
    eq, out_dates = [init_cap], [dts[start]]
    for t in range(start, L - 1):
        reb_cost = 0.0
        if (t - start) % step == 0:                       # rebalancement
            nw = _weights_at(A, rets, t, lookback, blackout_move, max_weight,
                             min_names, tgt_vol)
            if nw is not None:
                if band > 0 and w.sum() > 0:
                    nw = np.where(np.abs(nw - w) < band, w, nw)
                reb_cost = float((np.abs(nw - w) * rt).sum())  # #P0-3 : coût du turnover ce jour-là
                w = nw
        r_d = float((w * (A[:, t + 1] / A[:, t] - 1)).sum()) - reb_cost   # quotidien NET de coûts
        eq.append(eq[-1] * (1 + r_d))
        out_dates.append(dts[t + 1])
    if len(eq) < 30:
        return {"available": False}
    return {"available": True, "equity": [round(x, 2) for x in eq], "dates": out_dates}


def _motif(prev_i: float, w_i: float, d: float) -> str:
    """Motif lisible d'une variation de poids matérielle."""
    if prev_i <= 1e-4:
        return "entrée (univers qualité, risk-parity)"
    if w_i <= 1e-4:
        return "sortie (hors univers / blackout)"
    return "renforcement (risk-parity)" if d > 0 else "allègement (DD-target/risk-parity)"


def preset_trade_log(data: dict, quality: dict | None = None, asset_classes: dict | None = None,
                     dd_target: float = 0.35, band: float = 0.03, step: int = 21,
                     lookback: int = 120, top_k: int = 30, k_dd: float = 1.6,
                     blackout_move: float = 0.12, max_weight: float = 0.10,
                     min_names: int = 12, init_cap: float = 10000.0,
                     max_trades: int = 150) -> dict:
    """Journal des TRADES du preset : à chaque rebalancement, variations de poids → achats/ventes
    (date, symbole, sens, poids avant/après, notionnel ≈ Δpoids × capital). Net du turnover."""
    _ = quality, asset_classes  # compat API ; univers anti-fuite, coûts non appliqués ici
    g = _grille(data, lookback, step, top_k, min_names)
    if g is None:
        return {"available": False}
    universe, _dts, A = g
    L = A.shape[1]
    # Les dates PAR SYMBOLE deviennent inutiles : sur une grille commune sans trous, chaque
    # titre est coté à chaque date. Le marqueur ne peut plus tomber hors de la fenêtre du titre —
    # c'était le contournement d'un désalignement, pas une propriété souhaitable.
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
                trades.append({"date": _dts[t], "symbol": sym,
                               "side": "BUY" if d > 0 else "SELL",
                               "from": round(float(prev[i]), 4), "to": round(float(w[i]), 4),
                               "notional": round(abs(d) * init_cap, 2),
                               "reason": _motif(prev[i], w[i], d)})
        prev = w
    if not trades:
        return {"available": False}
    trades = sorted(trades, key=lambda x: x["date"], reverse=True)[:max_trades]
    per_year = 252.0 / step
    return {"available": True, "trades": trades, "n_rebalances": rebs,
            "turnover_annual": round(turn / rebs * per_year, 2) if rebs else 0.0}
