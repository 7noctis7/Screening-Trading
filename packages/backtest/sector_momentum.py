"""Cœur MOMENTUM SECTORIEL (rotation) — rester investi dans les secteurs les plus forts.

À chaque rebalancement (mensuel par défaut), on classe les secteurs par momentum 6 mois (126 j)
et on garde les `top_sectors` meilleurs. Dans ces secteurs, on équipondère les SOCIÉTÉS dont le
cours est au-dessus de leur MM50 (filtre de tendance) → on évite les contre-tendances. Point-in-
time, numpy pur. Rotation : un secteur qui sort/entre du classement est pris en compte.

But : variante ROBUSTE du « prendre le secteur n°1 chaque semaine » (trop concentré/whippy) →
formation 6 mois, rebalancement mensuel, 2 secteurs, filtre tendance. À comparer à QQQ par sweep.

ALIGNEMENT PAR DATE — migration du 31/08, la TROISIÈME occurrence du même défaut.

Ce module empilait POSITIONNELLEMENT (`fenetre_commune`) : les L dernières barres
de chaque titre, superposées, avec un calendrier pris sur la SEULE série la plus
longue. Un titre radié en 2018 versait donc des cours de 2018 dans des colonnes
étiquetées 2026, et le classement `closes[s][t] / closes[s][t - lookback] - 1`
comparait des rendements calculés sur des PÉRIODES CALENDAIRES DIFFÉRENTES au sein
d'un même secteur. Le preset avait été migré en #341, la production en #347 ; ce
cœur ne l'avait jamais été.

Mesuré avant correction sur la vraie base : 53,6 % de CAGR et 8908 % de rendement
total à 100 % de cœur — un résultat qui, s'il était réel, rendrait inutile tout le
reste du système. C'est le signe qu'on attaque, pas qu'on célèbre.
"""

from __future__ import annotations

import numpy as np

from packages.backtest.conviction_backtest import _stats
from packages.backtest.panel import aligner_par_date


def sector_momentum_equity_daily(data: dict, sectors: dict, asset_classes: dict | None = None,
                                 top_sectors: int = 2, lookback: int = 126, step: int = 21,
                                 init_cap: float = 10000.0, trend_filter: bool = True,
                                 min_per_sector: int = 2) -> dict:
    """Renvoie {available, equity, dates, current_sectors, current_holdings, weighting}."""
    ac = asset_classes or {}
    syms = [s for s, b in data.items()
            if b and len(b) > lookback + 2 * step and ac.get(s, "equity") in ("equity", "")
            and sectors.get(s)]
    if len(syms) < 5:
        return {"available": False}
    syms, dts, A, panel_diag = aligner_par_date(data, syms)
    if len(syms) < 5:
        return {"available": False}
    L = len(dts)
    closes = {s: A[i] for i, s in enumerate(syms)}
    ma50 = {s: _sma(closes[s], 50) for s in syms}
    by_sector: dict[str, list[str]] = {}
    for s in syms:
        by_sector.setdefault(sectors[s], []).append(s)
    by_sector = {k: v for k, v in by_sector.items() if len(v) >= min_per_sector}
    if len(by_sector) < top_sectors:
        return {"available": False}

    start = max(lookback, 50)
    cur_secs: list[str] = []
    holds: list[str] = []
    eq = [init_cap]
    out_dates = [dts[start]]
    for t in range(start, L - 1):
        if (t - start) % step == 0:                       # rotation sectorielle
            cur_secs, holds = _rebalance(closes, ma50, by_sector, t,
                                         lookback, top_sectors, trend_filter)
        r_d = _rendement_jour(closes, holds, t)
        eq.append(eq[-1] * (1 + r_d))
        out_dates.append(dts[t + 1])
    if len(eq) < 30:
        return {"available": False}
    return {"available": True, "equity": [round(x, 2) for x in eq], "dates": out_dates,
            "stats": _stats([eq[i + 1] / eq[i] - 1 for i in range(len(eq) - 1)], 252.0),
            "current_sectors": cur_secs, "current_holdings": holds, "weighting": "equal",
            # Profondeur EFFECTIVE : un ratio annualisé sans le nombre de pas qui l'a produit
            # n'est pas contestable, donc il ne vaut rien.
            "panel": panel_diag}


def _rebalance(closes: dict, ma50: dict, by_sector: dict, t: int, lookback: int,
               top_sectors: int, trend_filter: bool) -> tuple[list, list]:
    """Secteurs retenus et lignes détenues à `t`. Point-in-time : rien après `t`.

    Les comparaisons avec NaN valent False, donc un titre qui ne cote pas à `t` est
    naturellement écarté du filtre de tendance — y compris dans le repli, où il fallait
    l'exclure explicitement.
    """
    mom = {}
    for sec, membres in by_sector.items():
        rs = [closes[s][t] / closes[s][t - lookback] - 1 for s in membres
              if np.isfinite(closes[s][t]) and closes[s][t - lookback] > 0]
        if rs:
            mom[sec] = float(np.mean(rs))
    cur_secs = sorted(mom, key=lambda k: mom[k], reverse=True)[:top_sectors]
    holds = [s for sec in cur_secs for s in by_sector[sec]
             if (not trend_filter) or closes[s][t] > ma50[s][t]]
    if not holds:                                          # aucun titre en tendance
        holds = [s for sec in cur_secs for s in by_sector[sec]
                 if np.isfinite(closes[s][t])]
    return cur_secs, holds


def _rendement_jour(closes: dict, holds: list, t: int) -> float:
    """Rendement équipondéré du jour, sur les lignes RÉELLEMENT COTÉES à t et t+1.

    Depuis l'alignement par date, un titre radié devient NaN aux dates postérieures.
    Sans ce filtre, `np.mean` rendait NaN et la courbe restait NaN jusqu'au bout —
    défaut introduit par la migration et attrapé par `test_la_courbe_reste_exploitable`.

    BIAIS RÉSIDUEL, ASSUMÉ ET DOCUMENTÉ. Retirer la ligne radiée de la moyenne revient à
    répartir son poids sur les survivantes le jour même, donc à ÉCHAPPER à la perte de
    radiation. C'est optimiste. Le traitement exact demande les rendements de radiation
    (`data/delisted.csv`, `packages/data/survivorship`) et n'est pas fait ici : ce
    module reste donc INDICATIF, comme le rappelle déjà l'avertissement du sweep.
    """
    rs = [closes[s][t + 1] / closes[s][t] - 1 for s in holds
          if np.isfinite(closes[s][t]) and np.isfinite(closes[s][t + 1])
          and closes[s][t] > 0]
    return float(np.mean(rs)) if rs else 0.0


def _sma(x: np.ndarray, w: int) -> np.ndarray:
    """Moyenne mobile TOLÉRANTE AUX TROUS : moyenne des points DISPONIBLES.

    Depuis l'alignement par date, la matrice contient légitimement des NaN (un titre ne
    cote pas toutes les dates du panel). Or `np.cumsum` propage un NaN À L'INFINI : un
    seul jour manquant rendrait la MM50 NaN pour tout le reste de l'historique, et le
    filtre de tendance `cours > MM50` deviendrait faux à jamais. Le titre serait exclu
    en SILENCE, sans qu'aucun compteur ne le dise.

    On somme donc les points valides et on divise par LEUR NOMBRE, pas par `w`.
    """
    v = np.isfinite(x)
    if x.size < w:
        m = float(np.nanmean(x)) if v.any() else np.nan
        return np.full(x.size, m)
    cs = np.cumsum(np.insert(np.where(v, x, 0.0), 0, 0.0))
    cn = np.cumsum(np.insert(v.astype(float), 0, 0.0))
    nb = cn[w:] - cn[:-w]
    out = np.where(nb > 0, (cs[w:] - cs[:-w]) / np.maximum(nb, 1.0), np.nan)
    return np.concatenate([np.full(w - 1, out[0]), out])
