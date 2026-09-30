"""SMCLXTP-A à la place du satellite de production — même cœur, mêmes dates, mêmes frais.

Question : le portefeuille « cœur QQQ + satellite SMCLXTP-A » bat-il la production
(« cœur QQQ + preset ») ? Seul le satellite change :
  * décisions aux MÊMES dates que le rejeu de production (`cibles_rejouees`) ;
  * satellite = équipondéré de TOUS les titres de l'univers négociable où SMCLXTP-A est
    acheteur (LONG ouvert, pas encore de TP) — aucun paramètre de sélection à régler ;
  * même cœur (`avec_coeur`), même exécution J+1, même bande, mêmes frais (`simuler`).

RÈGLE ÉCRITE AVANT LA MESURE : SMCLXTP-A n'est MEILLEUR que si le ΔSharpe apparié
(SMCLXTP-A − production) est positif avec p < 0,05 ET que son maxDD n'est pas pire.
Sinon, la production est conservée. Un « meilleur » ne change rien sans décision explicite.
"""

from __future__ import annotations

from bisect import bisect_right

import numpy as np

from packages.backtest.panel import _jour


def etats_smc(data: dict) -> dict[str, tuple[list[str], np.ndarray]]:
    """État LONG de SMCLXTP-A par titre et par jour. `calculer` est causal : l'état du
    jour i ne dépend que des barres ≤ i (testé par troncature)."""
    from packages.backtest.scenarios_horizons import depuis_evenements
    from packages.indicators.smc_lux_tp import calculer
    out = {}
    for sym, barres in data.items():
        if len(barres) < 3:
            continue
        h, lo, c = (np.array([float(getattr(b, k)) for b in barres])
                    for k in ("high", "low", "close"))
        r = calculer(h, lo, c)
        out[sym] = ([_jour(b) for b in barres],
                    depuis_evenements(r["long_signal"], r["take_profit_signal"]))
    return out


def poids_smc(etats: dict, jour: str) -> dict[str, float]:
    """Équipondéré des titres LONG à la clôture de `jour` (dernière barre ≤ jour)."""
    longs = []
    for sym, (jours, etat) in etats.items():
        i = bisect_right(jours, jour) - 1
        if i >= 0 and etat[i]:
            longs.append(sym)
    return {s: 1.0 / len(longs) for s in sorted(longs)} if longs else {}


def verdict(delta: dict, dd_smc: float, dd_prod: float) -> str:
    """Applique la règle pré-enregistrée ; aucun autre critère n'est admis après lecture."""
    if not delta.get("disponible"):
        return "INDÉTERMINÉ (ΔSharpe non calculable)"
    if delta["verdict"] == "meilleur" and dd_smc >= dd_prod - 1e-9:
        return "SMCLXTP-A MEILLEUR (décision explicite requise)"
    return "PRODUCTION CONSERVÉE"


def comparer_satellites(data: dict, prep: tuple, *, coeur: dict | None,
                        classes: dict | None) -> dict:
    """Production vs SMCLXTP-A, à partir des décisions de production déjà rejouées."""
    from packages.backtest.preset_rejeu import (
        _prix_par_jour,
        _stats_courbe,
        avec_coeur,
        comparer_sharpe,
        simuler,
    )
    cal, brutes, cibles = prep
    etats = etats_smc(data)
    satellites = [(j, poids_smc(etats, j)) for j, _ in brutes]
    prix = _prix_par_jour(data)
    prod = simuler(cibles, prix, cal, classes=classes)
    smc = simuler([(j, avec_coeur(w, coeur)) for j, w in satellites], prix, cal,
                  classes=classes)
    if not (prod.get("available") and smc.get("available")):
        return {"available": False, "raison": "aucune exécution dans le calendrier"}
    courbes = {k: [v / r["equity"][0] for v in r["equity"]]
               for k, r in (("production", prod), ("smclxtp", smc))}
    stats = {k: _stats_courbe(v) for k, v in courbes.items()}
    delta = comparer_sharpe(courbes["production"], courbes["smclxtp"])
    n_longs = [len(w) for _, w in satellites]
    return {"available": True, "dates": prod["dates"], "stats": stats, "delta": delta,
            "frais": {"production": prod["frais"], "smclxtp": smc["frais"]},
            "n_ordres": {"production": prod["n_ordres"], "smclxtp": smc["n_ordres"]},
            "titres_long_moyen": float(np.mean(n_longs)) if n_longs else 0.0,
            "decisions_sans_long": sum(1 for n in n_longs if n == 0),
            "verdict": verdict(delta, stats["smclxtp"]["max_drawdown"],
                               stats["production"]["max_drawdown"])}
