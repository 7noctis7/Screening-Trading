"""Backtest « LONG au signal, sortie au signal TP » d'un indicateur qui signale au close.

Règles d'exécution, écrites AVANT tout chiffre (SMCLXTP-A, 30/09) :
  * un signal naît au CLOSE de t (un pivot n'est confirmé qu'au close) : l'ordre part à
    l'OUVERTURE de t+1, jamais au prix qui a produit le signal ;
  * une position à la fois, 100 % du capital du titre, gains réinvestis (10 000 $ au
    départ) ; un LONG reçu en position est ignoré, un TP reçu à plat aussi ;
  * pas de stop pour SMCLXTP-A (il n'en a pas) ; les stratégies du bot qui fixent un stop
    et une cible au close du signal les voient honorés EN SÉANCE, avec l'hypothèse
    défavorable : gap sous le stop → ouverture, stop avant cible dans la même barre,
    cible au prix de la cible (jamais mieux) ;
  * frais à CHAQUE jambe (`cout`, fraction du notionnel, barème du dépôt par classe) ;
  * une position encore ouverte à la fin est marquée au dernier close — ce n'est pas un
    trade clôturé (même convention que le Strategy Tester de TradingView).
Les KPI réutilisent les formules uniques du dépôt (`portfolio.metrics`).
"""

from __future__ import annotations

import math
from bisect import bisect_left
from dataclasses import dataclass
from datetime import datetime

import numpy as np

CAPITAL = 10_000.0


@dataclass(frozen=True)
class Trade:
    entree_jour: str
    sortie_jour: str
    prix_entree: float
    prix_sortie: float
    capital: float
    pnl: float
    pnl_pct: float
    jours: float
    motif_sortie: str = "signal"


def _jours_entre(a: str, b: str) -> float:
    """Jours (fractionnaires en intraday) entre deux horodatages ISO."""
    return (datetime.fromisoformat(b) - datetime.fromisoformat(a)).total_seconds() / 86400.0


def _niveau(v, t: int) -> float | None:
    if v is None:
        return None
    x = float(v[t])
    return x if math.isfinite(x) else None


def _toucher(pos: dict, t: int, o, haut, bas) -> tuple[float, str] | None:
    """(prix, motif) si le stop ou la cible de la position est touché en séance `t`."""
    if pos.get("stop") is not None and bas is not None and bas[t] <= pos["stop"]:
        return min(float(o[t]), pos["stop"]), "stop"
    if pos.get("cible") is not None and haut is not None and haut[t] >= pos["cible"]:
        return pos["cible"], "cible"
    return None


def simuler(jours: list[str], o, c, long_sig, tp_sig, *, debut: str, cout: float,
            capital: float = CAPITAL, haut=None, bas=None, stops=None,
            cibles=None) -> dict:
    """Déroule les signaux à partir de `debut` (les barres antérieures ne servent qu'au
    calcul de l'indicateur, en amont). Equity marquée au close de chaque barre.

    `stops`/`cibles` (optionnels, NaN = aucun) : niveaux fixés au close du signal LONG,
    honorés dès la barre d'entrée ; ils exigent `haut` et `bas`."""
    i0 = bisect_left(jours, debut)
    cash, pos, ordre = float(capital), None, None
    trades, dates, equity, investi = [], [], [], []
    for t in range(i0, len(jours)):
        if ordre is not None and ordre[0] == "achat" and pos is None:
            pos = {"parts": cash / (o[t] * (1 + cout)), "jour": jours[t], "px": float(o[t]),
                   "cap": cash, "stop": ordre[1], "cible": ordre[2]}
            cash = 0.0
        elif ordre == ("vente",) and pos is not None:
            cash, pos = _sortir(pos, jours[t], float(o[t]), "signal", cout, trades), None
        ordre = None
        touche = _toucher(pos, t, o, haut, bas) if pos is not None else None
        if touche is not None:
            cash, pos = _sortir(pos, jours[t], touche[0], touche[1], cout, trades), None
        dates.append(jours[t])
        equity.append(cash + (pos["parts"] * float(c[t]) if pos else 0.0))
        investi.append(pos is not None)
        if pos is not None and tp_sig[t]:
            ordre = ("vente",)
        elif pos is None and long_sig[t]:
            ordre = ("achat", _niveau(stops, t), _niveau(cibles, t))
    ouvert = None if pos is None else {"entree_jour": pos["jour"], "prix_entree": pos["px"],
                                       "valeur": equity[-1] if equity else 0.0}
    return {"dates": dates, "equity": equity, "trades": trades, "ouvert": ouvert,
            "investi": investi, "clotures": [float(x) for x in c[i0:]]}


def _sortir(pos: dict, jour: str, prix: float, motif: str, cout: float,
            trades: list) -> float:
    cash = pos["parts"] * prix * (1 - cout)
    trades.append(Trade(pos["jour"], jour, pos["px"], prix, pos["cap"], cash - pos["cap"],
                        cash / pos["cap"] - 1.0, _jours_entre(pos["jour"], jour), motif))
    return cash


def _stats_courbe(eq: list[float], dates: list[str], par_an: float) -> dict:
    from packages.portfolio.metrics import max_drawdown, sharpe, sortino
    annees = _jours_entre(dates[0], dates[-1]) / 365.25 if len(dates) > 1 else 0.0
    cagr = (eq[-1] / eq[0]) ** (1 / annees) - 1 if annees > 0 and eq[-1] > 0 else math.nan
    return {"cagr": cagr, "max_drawdown": max_drawdown(eq),
            "sharpe": sharpe(eq, ppy=int(par_an)), "sortino": sortino(eq, ppy=int(par_an)),
            "rendement_total": eq[-1] / eq[0] - 1}


def kpis(res: dict, par_an: float) -> dict:
    """KPI de la stratégie (trades CLÔTURÉS pour les stats de trades) et du buy & hold."""
    from packages.portfolio.metrics import trade_stats
    trades, eq, dates = res["trades"], res["equity"], res["dates"]
    st = trade_stats([t.pnl for t in trades])
    moy = (lambda xs: float(np.mean(xs)) if xs else math.nan)     # noqa: E731
    perte = st.get("avg_loss", 0.0)
    bh = [CAPITAL * x / res["clotures"][0] for x in res["clotures"]]
    return {"periode": f"{dates[0]} → {dates[-1]}", "trades": st["n"],
            "win_rate": st["win_rate"] if trades else math.nan,
            "duree_moyenne_jours": moy([t.jours for t in trades]),
            "profit_factor": st["profit_factor"] if trades else math.nan,
            "payoff": (st["avg_win"] / abs(perte)) if trades and perte else math.nan,
            "pnl_moyen": moy([t.pnl for t in trades]),
            "pnl_moyen_pct": moy([t.pnl_pct for t in trades]),
            "exposition": float(np.mean(res["investi"])) if res["investi"] else 0.0,
            "position_ouverte": res["ouvert"],
            **_stats_courbe(eq, dates, par_an),
            "buy_and_hold": _stats_courbe(bh, dates, par_an)}
