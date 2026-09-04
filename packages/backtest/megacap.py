"""Rotation MÉGA-CAPS : détenir les N plus grosses sociétés, rééquilibrées quand le classement
change. Proxy de « taille » = dollar-volume moyen récent (prix × volume) — disponible dans l'OHLCV,
contrairement à la capitalisation historique (souvent indisponible). Re-classé à chaque période →
les entrées/sorties suivent les changements de classement. Équipondéré, point-in-time. numpy pur.
"""

from __future__ import annotations

import numpy as np

from packages.backtest.conviction_backtest import _stats
from packages.backtest.panel import fenetre_commune

# Doubles classes d'actions (même SOCIÉTÉ) → on n'en garde qu'UNE dans le top-N (sinon Alphabet,
# Fox… sont comptés deux fois et volent une place). On garde la 1re rencontrée (= plus grosse).
_DUAL_CLASS = {"GOOG": "ALPHABET", "GOOGL": "ALPHABET", "FOX": "FOX", "FOXA": "FOX",
               "NWS": "NEWSCORP", "NWSA": "NEWSCORP", "BRK-A": "BERKSHIRE", "BRK-B": "BERKSHIRE",
               "BRK.A": "BERKSHIRE", "BRK.B": "BERKSHIRE", "UA": "UNDERARMOUR", "UAA": "UNDERARMOUR"}


def _company_key(sym: str) -> str:
    return _DUAL_CLASS.get(sym.upper(), sym.upper())


def _rendement_pondere(closes: dict, poids: dict, cur: list, t: int) -> float:
    """Rendement pondéré du jour, sur les seules lignes RÉELLEMENT COTÉES à t et t+1.

    CORRECTIF DU 04/09, ET C'EST UNE PANNE VISIBLE EN PRODUCTION. Ce calcul n'avait
    AUCUNE garde. Depuis l'alignement par date, la matrice contient légitimement des NaN
    (un titre ne cote pas toutes les dates du panel) — et `x * nan` vaut nan, donc **un
    seul cours manquant rendait le rendement du jour NaN, l'équity NaN, et toute la fin
    de la courbe avec**. `dump_static._clean` convertit ensuite NaN en `None`, que le
    front lit comme zéro : le tableau de bord affichait **CAGR −100 %, pire baisse
    −100 %** avec un Sharpe de 0,25 et un Sortino de 0,18 — RESTÉS POSITIFS, puisqu'ils
    sont calculés sur les rendements avant nettoyage. Cette combinaison est impossible
    pour une vraie courbe, et c'est elle qui a permis de remonter jusqu'ici.

    `sector_momentum._rendement_jour` portait déjà cette garde ; celui-ci ne l'avait
    jamais reçue. On renormalise les poids sur les lignes cotées : les ignorer sans
    renormaliser supposerait que la part manquante fait 0 % ce jour-là — un rendement
    inventé, pas une absence."""
    valides = [s for s in cur
               if np.isfinite(closes[s][t]) and np.isfinite(closes[s][t + 1])
               and closes[s][t] > 0]
    total = sum(poids.get(s, 0.0) for s in valides)
    if not valides or total <= 0:
        return 0.0
    return float(sum(poids.get(s, 0.0) / total * (closes[s][t + 1] / closes[s][t] - 1)
                     for s in valides))


def _top_unique(ranked: list[str], top_n: int) -> list[str]:
    """top_n SOCIÉTÉS distinctes (déduplique les doubles classes d'actions)."""
    out: list[str] = []
    seen: set[str] = set()
    for s in ranked:
        ck = _company_key(s)
        if ck in seen:
            continue
        seen.add(ck)
        out.append(s)
        if len(out) >= top_n:
            break
    return out



def megacap_rotation(data: dict, asset_classes: dict | None = None, top_n: int = 10,
                     step: int = 63, lookback: int = 63) -> dict:
    """Top-N par dollar-volume, rééquilibré tous les `step` jours (rotation sur le classement)."""
    ac = asset_classes or {}
    syms = [s for s, b in data.items()
            if b and len(b) > lookback + 2 * step and ac.get(s, "equity") in ("equity", "etf")]
    if len(syms) < top_n:
        return {"available": False}
    syms, L, panel_diag = fenetre_commune(data, syms, min_noms=top_n)
    if len(syms) < top_n:
        return {"available": False}
    closes = {s: np.asarray([b.close for b in data[s]][-L:], float) for s in syms}
    dvol = {s: closes[s] * np.asarray([getattr(b, "volume", 0.0) for b in data[s]][-L:], float)
            for s in syms}
    port, prev, turn, rebs = [], set(), 0.0, 0
    last_top: list[str] = []
    for t in range(max(lookback, 50), L - 1, step):
        score = {s: float(np.mean(dvol[s][max(0, t - lookback):t])) for s in syms}
        top = _top_unique(sorted(score, key=lambda s: score[s], reverse=True), top_n)
        nxt = min(t + step, L - 1)
        port.append(float(np.mean([closes[s][nxt] / closes[s][t] - 1 for s in top])))
        turn += len(set(top) ^ prev) / (2 * top_n)
        prev, last_top, rebs = set(top), top, rebs + 1
    if rebs < 3:
        return {"available": False}
    per_year = 252.0 / step
    return {"available": True, "stats": _stats(port, per_year), "n_rebalances": rebs,
            "step_days": step, "top_n": top_n,
            "turnover_per_rebal": round(turn / rebs, 2), "current_top": last_top,
            "panel": panel_diag}


def megacap_equity_daily(data: dict, asset_classes: dict | None = None, top_n: int = 10,
                         step: int = 63, lookback: int = 63, init_cap: float = 10000.0,
                         include_etf: bool = False, market_caps: dict | None = None) -> dict:
    """Courbe d'equity QUOTIDIENNE de la rotation top-N méga-caps → cœur mélangé au preset.

    Classement & PONDÉRATION par MARKET CAP réelle si `market_caps` est fourni (comme un vrai
    indice cap-weighted), sinon repli proxy dollar-volume + équipondéré. Re-classé tous les `step`
    jours → une société qui sort/entre du top-N est prise en compte (rotation). SOCIÉTÉS
    uniquement par défaut (ETF exclus). Anti-fuite : panier classé EN t pour le rendement t→t+1.
    Renvoie {available, equity, dates, current_top, current_weights, weighting}."""
    ac = asset_classes or {}
    _ok = ("equity", "etf") if include_etf else ("equity", "")
    syms = [s for s, b in data.items()
            if b and len(b) > lookback + 2 * step and ac.get(s, "equity") in _ok]
    # market caps dispo pour assez de titres → on classera/pondérera par cap RÉELLE
    use_cap = bool(market_caps) and len([s for s in syms if s in market_caps]) >= top_n
    if use_cap:
        syms = [s for s in syms if s in market_caps]
    if len(syms) < top_n:
        return {"available": False}
    # COURBE LONGUE (même règle que le preset) : on écarte les historiques courts (IPO récentes)
    # qui tronqueraient toute la courbe au plus court → la fenêtre commune remonte aussi loin que
    # les sociétés établies (sinon une IPO 2023 ramène tout le dashboard à 2023).
    syms, L, panel_diag = fenetre_commune(data, syms, min_noms=top_n)
    if len(syms) < top_n:
        return {"available": False}
    closes = {s: np.asarray([b.close for b in data[s]][-L:], float) for s in syms}
    ref = max(syms, key=lambda s: len(data[s]))
    dts = [b.ts.isoformat() for b in data[ref]][-L:]
    # métrique de TAILLE : market cap réelle (cap-weighted) si dispo, sinon proxy dollar-volume
    size: dict[str, np.ndarray] = {}
    if use_cap:
        from packages.data.market_cap import shares_asof
        for s in syms:
            sh = shares_asof(market_caps[s], dts)
            size[s] = np.nan_to_num(sh * closes[s], nan=0.0)
    else:                                                 # repli : dollar-volume (proxy de taille)
        size = {s: closes[s] * np.asarray([getattr(b, "volume", 0.0) for b in data[s]][-L:], float)
                for s in syms}
    start = max(lookback, 50)
    cur: list[str] = []
    curw: dict[str, float] = {}
    eq = [init_cap]
    out_dates = [dts[start]]
    for t in range(start, L - 1):
        if (t - start) % step == 0:                       # re-classement (rotation entrée/sortie)
            if use_cap:
                score = {s: float(size[s][t]) for s in syms}            # cap ponctuelle
            else:
                score = {s: float(np.mean(size[s][max(0, t - lookback):t])) for s in syms}
            cur = _top_unique(sorted(score, key=lambda s: score[s], reverse=True), top_n)
            if use_cap:                                   # pondération PAR CAP (renormalisée au top-N)
                tot = sum(max(0.0, score[s]) for s in cur) or 1.0
                curw = {s: max(0.0, score[s]) / tot for s in cur}
            else:                                         # repli : équipondéré
                curw = {s: 1.0 / len(cur) for s in cur} if cur else {}
        r_d = _rendement_pondere(closes, curw, cur, t)
        eq.append(eq[-1] * (1 + r_d))
        out_dates.append(dts[t + 1])
    if len(eq) < 30:
        return {"available": False}
    return {"available": True, "equity": [round(x, 2) for x in eq], "dates": out_dates,
            "current_top": cur, "current_weights": {s: round(w, 4) for s, w in curw.items()},
            "weighting": "market_cap" if use_cap else "dollar_volume",
            "panel": panel_diag}
