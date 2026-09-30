"""Backtest « LONG au signal, sortie au signal TP » d'un indicateur qui signale au close.

Règles d'exécution, écrites AVANT tout chiffre (SMCLXTP-A, 30/09) :
  * un signal naît au CLOSE de t (un pivot n'est confirmé qu'au close) : l'ordre part à
    l'OUVERTURE de t+1, jamais au prix qui a produit le signal ;
  * une position à la fois, 100 % du capital du titre, gains réinvestis (10 000 $ au
    départ) ; un LONG reçu en position est ignoré, un TP reçu à plat aussi ;
  * pas de stop : l'indicateur n'en a pas, la seule sortie est son signal TP ;
  * frais à CHAQUE jambe (`cout`, fraction du notionnel, barème du dépôt par classe) ;
  * une position encore ouverte à la fin est marquée au dernier close — ce n'est pas un
    trade clôturé (même convention que le Strategy Tester de TradingView).
Les KPI réutilisent les formules uniques du dépôt (`portfolio.metrics`).
"""

from __future__ import annotations

import math
from bisect import bisect_left
from dataclasses import dataclass
from datetime import date

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
    jours: int


def _jours_entre(a: str, b: str) -> int:
    return (date.fromisoformat(b[:10]) - date.fromisoformat(a[:10])).days


def simuler(jours: list[str], o, c, long_sig, tp_sig, *, debut: str, cout: float,
            capital: float = CAPITAL) -> dict:
    """Déroule les signaux à partir de `debut` (les barres antérieures ne servent qu'au
    calcul de l'indicateur, en amont). Equity marquée au close de chaque barre."""
    i0 = bisect_left(jours, debut)
    cash, parts, entree, ordre = float(capital), 0.0, None, None
    trades, dates, equity, investi = [], [], [], []
    for t in range(i0, len(jours)):
        if ordre == "achat" and parts == 0.0:
            parts = cash / (o[t] * (1 + cout))
            entree, cash = (jours[t], float(o[t]), cash), 0.0
        elif ordre == "vente" and parts > 0.0:
            cash = parts * o[t] * (1 - cout)
            j0, px0, cap = entree
            trades.append(Trade(j0, jours[t], px0, float(o[t]), cap, cash - cap,
                                cash / cap - 1.0, _jours_entre(j0, jours[t])))
            parts, entree = 0.0, None
        ordre = None
        dates.append(jours[t])
        equity.append(cash + parts * float(c[t]))
        investi.append(parts > 0.0)
        if parts > 0.0 and tp_sig[t]:
            ordre = "vente"
        elif parts == 0.0 and long_sig[t]:
            ordre = "achat"
    ouvert = None if entree is None else {"entree_jour": entree[0], "prix_entree": entree[1],
                                          "valeur": equity[-1] if equity else 0.0}
    return {"dates": dates, "equity": equity, "trades": trades, "ouvert": ouvert,
            "investi": investi, "clotures": [float(x) for x in c[i0:]]}


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
