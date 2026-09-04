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

# Coût ALLER SIMPLE sur le notionnel échangé à chaque rotation — même convention que
# `coeur_multi_actifs.COUT_BPS`. AUDIT DU 04/09 : ce module n'en appliquait AUCUN, alors
# qu'il tourne mensuellement sur deux secteurs entiers et qu'il est comparé à QQQ, un
# buy-and-hold dont le turnover est nul. Comparer une rotation gratuite à une détention
# gratuite avantage mécaniquement la rotation. Effet MESURÉ sur panneau synthétique
# (24 titres, 4 secteurs, 9,5 ans) : 0,64 point de CAGR. Réel, mais ce n'est PAS
# l'explication des 55,5 % — voir le biais du survivant plus bas.
COUT_BPS = 5.0


def sector_momentum_equity_daily(data: dict, sectors: dict, asset_classes: dict | None = None,
                                 top_sectors: int = 2, lookback: int = 126, step: int = 21,
                                 init_cap: float = 10000.0, trend_filter: bool = True,
                                 min_per_sector: int = 2,
                                 cout_bps: float = COUT_BPS) -> dict:
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
    frais_cumules = 0.0
    for t in range(start, L - 1):
        cout = 0.0
        if (t - start) % step == 0:                       # rotation sectorielle
            avant = holds
            cur_secs, holds = _rebalance(closes, ma50, by_sector, t,
                                         lookback, top_sectors, trend_filter)
            cout = cout_bps / 1e4 * _turnover(avant, holds)
            frais_cumules += cout
        r_d = _rendement_jour(closes, holds, t)
        eq.append(eq[-1] * (1 + r_d) * (1 - cout))
        out_dates.append(dts[t + 1])
    if len(eq) < 30:
        return {"available": False}
    return {"available": True, "equity": [round(x, 2) for x in eq], "dates": out_dates,
            "stats": _stats([eq[i + 1] / eq[i] - 1 for i in range(len(eq) - 1)], 252.0),
            "current_sectors": cur_secs, "current_holdings": holds, "weighting": "equal",
            # Les frais sont PUBLIÉS : un backtest qui tait ce qu'il a payé ne se
            # compare pas à un autre qui paie autre chose.
            "cout_bps": cout_bps, "frais_cumules": round(frais_cumules, 4),
            # LE CHIFFRE NE VOYAGE PLUS SANS SON BIAIS (audit du 04/09). Voir
            # `_biais_survivant` : sur un univers de survivants, un CAGR de rotation
            # sectorielle n'est pas un résultat, c'est un artefact de sélection.
            "biais_survivant": _biais_survivant(syms),
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


def _biais_survivant(syms: list[str]) -> dict:
    """Statut du biais du survivant POUR CET UNIVERS — attaché au résultat, pas à côté.

    AUDIT DU 04/09, ET C'EST LA CAUSE PRINCIPALE DES 55,5 % DE CAGR. Le nettoyage
    d'univers de `build_snapshot` retire tout titre dont la dernière barre a plus de dix
    jours — donc **tous les délistés, avant que le moindre backtest ne tourne**. Ce cœur
    classe ensuite des secteurs sur 9,4 ans en ne voyant que les sociétés qui existent
    ENCORE aujourd'hui : les faillites et les radiations qui auraient vidé les paniers
    sectoriels ont été écartées par construction.

    Les coûts de transaction, absents eux aussi, ne pèsent que 0,64 point de CAGR
    (mesuré) : ils ne sauraient expliquer un tel chiffre. Le biais de sélection, si.

    `survivorship_audit` savait déjà répondre « ÉLEVÉ — univers survivant uniquement ».
    Il n'était simplement jamais attaché au résultat, si bien que le CAGR voyageait seul
    jusqu'au tableau de bord. Un chiffre séparé de son biais se lit comme un résultat.

    CE QU'ON MESURE, ET POURQUOI PAS `survivorship_audit` TEL QUEL. Cet audit rapporte
    le nombre de délistés CONNUS au nombre d'actifs : avec 3 titres et 43 délistés au
    catalogue, il annonce « corrigé (partiel) » et une couverture de 93,5 %. Il répond à
    « connaît-on des délistés ? », pas à « sont-ils DANS le panneau ? ». Ici seule la
    seconde question compte : un délisté absent du panneau ne corrige rien.

    On compte donc les symboles délistés RÉELLEMENT présents dans l'univers du backtest.
    Zéro présent → biais ÉLEVÉ, quel que soit le catalogue.

    Best-effort : catalogue illisible → on le DIT, on ne suppose pas l'univers sain."""
    try:
        from packages.data.survivorship import load_delisted
        catalogue = {d["symbol"] for d in load_delisted()}
    except Exception as e:  # noqa: BLE001
        return {"available": False, "severite": "INCONNU — catalogue illisible",
                "motif": str(e)[:80]}
    presents = sorted(catalogue & set(syms))
    if not presents:
        severite = ("ÉLEVÉ — aucun délisté dans le panneau : le classement sectoriel\n"
                    "        ne voit que des sociétés encore cotées aujourd'hui")
    else:
        severite = (f"partiel — {len(presents)} délisté(s) présent(s) "
                    f"sur {len(catalogue)}")
    return {"available": True, "n_univers": len(syms), "n_catalogue": len(catalogue),
            "n_delistes_dans_le_panneau": len(presents), "exemples": presents[:5],
            "severite": severite}


def _turnover(avant: list[str], apres: list[str]) -> float:
    """Notionnel échangé pour passer d'un panier équipondéré à l'autre, en fraction.

    Somme des |Δpoids|. Une rotation complète (aucun titre commun) vaut 2,0 : on vend
    tout (1,0) et on rachète tout (1,0). Le premier rebalancement part de rien et vaut
    donc 1,0 — l'achat initial, qui se paie aussi."""
    if not apres:
        return 0.0
    wa = dict.fromkeys(avant, 1.0 / len(avant)) if avant else {}
    wb = dict.fromkeys(apres, 1.0 / len(apres))
    return sum(abs(wb.get(s, 0.0) - wa.get(s, 0.0)) for s in set(wa) | set(wb))


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
    # LE PRÉFIXE EST UN LOOK-AHEAD DORMANT (audit du 04/09). Les `w-1` premières cases
    # reçoivent `out[0]`, c'est-à-dire la moyenne des jours 0..w-1 : lue à t=10, elle
    # contient l'avenir. Elle n'est jamais lue aujourd'hui — la boucle démarre à
    # `max(lookback, 50)` = 126 — mais rien ne le garantit : un `lookback` inférieur à
    # `w` réveillerait la fuite en silence. NaN plutôt que le futur : une comparaison
    # avec NaN vaut False, donc le titre est écarté du filtre au lieu d'être admis sur
    # une valeur qu'on ne pouvait pas connaître.
    return np.concatenate([np.full(w - 1, np.nan), out])
