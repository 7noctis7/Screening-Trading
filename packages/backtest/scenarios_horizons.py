"""Grille horizons × stratégies × sorties × fréquences — config/horizons/2026-09-30_horizons.yaml.

Une stratégie est réduite à son ÉTAT désiré (long / à plat), lu sur le passé seul. La
FRÉQUENCE dit quand cet état est relu et exécuté (dernière séance de la période, ordre à
l'ouverture suivante). La SORTIE dit ce qui ferme une position :
  * `signal`        l'état de la stratégie repasse à plat ;
  * `tp_3atr`       idem, plus une prise de profit posée à +3 ATR (séance, tous les jours) ;
  * `suiveur_3atr`  idem, plus un stop Chandelier à 3 ATR (séance, tous les jours) ;
  * `tendance_mm200` À LA PLACE du signal : clôture sous la MM200 ; pas de rachat sous elle.
Exécution et frais : `signal_long_tp.simuler`, identiques pour tous les scénarios.
"""

from __future__ import annotations

from datetime import date

import numpy as np

FREQUENCES = ("barre", "jour", "semaine", "mois", "trimestre", "annee")
_CLE = {"jour": lambda d: d.toordinal(), "semaine": lambda d: d.isocalendar()[:2],
        "mois": lambda d: (d.year, d.month), "trimestre": lambda d: (d.year, (d.month - 1) // 3),
        "annee": lambda d: d.year}


def decisions(jours: list[str], frequence: str) -> np.ndarray:
    """Vrai à la dernière séance de chaque période présente dans les données."""
    if frequence not in FREQUENCES:
        raise ValueError(f"fréquence inconnue : {frequence} ({', '.join(FREQUENCES)})")
    if frequence == "barre":
        return np.ones(len(jours), bool)
    cles = [_CLE[frequence](date.fromisoformat(j[:10])) for j in jours]
    return np.array([cles[t] != cles[t + 1] for t in range(len(cles) - 1)] + [True], bool)


def depuis_evenements(long_: np.ndarray, flat: np.ndarray) -> np.ndarray:
    """Événements LONG / FLAT → état ; même règle que le moteur (on sort avant d'entrer)."""
    etat_, dedans = np.zeros(len(long_), bool), False
    for t in range(len(long_)):
        if dedans and flat[t]:
            dedans = False
        elif not dedans and long_[t]:
            dedans = True
        etat_[t] = dedans
    return etat_


def moyenne_mobile(c: np.ndarray, n: int) -> np.ndarray:
    out = np.full(c.size, np.nan)
    if c.size >= n:
        cs = np.concatenate([[0.0], np.cumsum(c)])
        out[n - 1:] = (cs[n:] - cs[:-n]) / n
    return out


def etat(nom: str, bars: list, par_an: float) -> np.ndarray:
    """État désiré à chaque barre, sur les seules barres ≤ t."""
    c = np.array([b.close for b in bars], float)
    with np.errstate(invalid="ignore"):
        if nom == "tendance_mm200":
            return c > moyenne_mobile(c, 200)
        if nom == "momentum_12_1":
            n12, n1 = int(round(par_an)), max(1, int(round(par_an / 12)))
            mom = np.full(c.size, np.nan)
            mom[n12:] = c[n12 - n1:c.size - n1] / c[:c.size - n12] - 1.0
            return mom > 0
    from packages.backtest.comparaison_strategies import signaux
    s = signaux(nom, bars)
    return depuis_evenements(s["long"], s["flat"])


def construire(etat_: np.ndarray, decision: np.ndarray, close: np.ndarray,
               sma200: np.ndarray, atr: np.ndarray, sortie: str, *, k_tp: float) -> dict:
    """Signaux du moteur pour un couple (stratégie, sortie) à une fréquence donnée."""
    with np.errstate(invalid="ignore"):
        if sortie == "tendance_mm200":
            long_ = decision & etat_ & (close >= sma200)
            flat = decision & (close < sma200)
        else:
            long_, flat = decision & etat_, decision & ~etat_
    cibles = close + k_tp * atr if sortie == "tp_3atr" else np.full(close.size, np.nan)
    return {"long": long_, "flat": flat, "cibles": cibles}


def _rendements(eq: list[float]) -> np.ndarray:
    e = np.asarray(eq, float)
    return e[1:] / e[:-1] - 1.0


def grille_actif(bars: list, classe: str, g: dict, *, debut: str, par_an: float) -> dict:
    """Tous les scénarios d'un actif : KPI, horizons, et la matrice des rendements (PBO)."""
    from packages.backtest.horizons_stats import fenetres
    from packages.backtest.signal_long_tp import kpis, simuler
    from packages.execution.costs import CostModel
    from packages.indicators.volatility import ATR
    jours = [b.ts.date().isoformat() if b.timeframe == "1d" else b.ts.isoformat()
             for b in bars]
    o, h, lo, c = (np.array([getattr(b, k) for b in bars], float)
                   for k in ("open", "high", "low", "close"))
    atr = np.asarray(ATR(int(g["atr"])).compute(bars), float)
    sma200, cout = moyenne_mobile(c, 200), CostModel.for_asset_class(classe).round_trip_bps / 2e4
    etats = {nom: etat(nom, bars, par_an) for nom in g["strategies"]}
    decs = {f: decisions(jours, f) for f in g["frequences"]}
    pas = max(1, int(round(g["pas_fenetres_jours"] * par_an / 252)))
    lignes, colonnes, bh = [], [], None
    for nom, e in etats.items():
        for sortie in g["sorties"]:
            for f in g["frequences"]:
                s = construire(e, decs[f], c, sma200, atr, sortie, k_tp=float(g["k_tp"]))
                sv = (float(g["k_suiveur"]), atr) if sortie == "suiveur_3atr" else None
                r = simuler(jours, o, c, s["long"], s["flat"], debut=debut, cout=cout,
                            haut=h, bas=lo, cibles=s["cibles"], suiveur=sv)
                k = kpis(r, par_an)
                bh = bh or {**k["buy_and_hold"], "horizons": {
                    H: fenetres(r["clotures"], r["clotures"], r["dates"], H, pas)
                    for H in g["horizons_annees"]}}
                lignes.append(_ligne(nom, sortie, f, k, r, g, pas))
                colonnes.append(_rendements(r["equity"]))
    return {"lignes": lignes, "R": np.column_stack(colonnes), "buy_and_hold": bh}


def _ligne(nom: str, sortie: str, f: str, k: dict, r: dict, g: dict, pas: int) -> dict:
    from packages.backtest.horizons_stats import fenetres
    return {"id": f"{nom}|{sortie}|{f}", "strategie": nom, "sortie": sortie, "frequence": f,
            **{m: k[m] for m in ("trades", "win_rate", "duree_moyenne_jours", "profit_factor",
                                 "sharpe", "sortino", "cagr", "max_drawdown",
                                 "pnl_moyen_pct", "exposition")},
            **risque_et_rotation(k, r),
            "horizons": {H: fenetres(r["equity"], r["clotures"], r["dates"], H, pas)
                         for H in g["horizons_annees"]}}


def risque_et_rotation(k: dict, r: dict) -> dict:
    """Calmar (CAGR / |maxDD|) et turnover annualisé : notionnel négocié (entrée + sortie
    des trades clôturés) rapporté à l'equity moyenne, par an."""
    from datetime import datetime
    dd, eq = k.get("max_drawdown") or 0.0, np.asarray(r["equity"], float)
    calmar = k["cagr"] / abs(dd) if dd < 0 and np.isfinite(k["cagr"]) else float("nan")
    d0, d1 = (datetime.fromisoformat(r["dates"][i]) for i in (0, -1))
    annees = max((d1 - d0).days / 365.25, 1e-9)
    negocie = sum(t.capital + (t.capital + t.pnl) for t in r["trades"])
    return {"calmar": calmar, "turnover_annuel": negocie / float(eq.mean()) / annees}
