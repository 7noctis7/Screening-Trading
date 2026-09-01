#!/usr/bin/env python3
"""Gestion de SORTIE : quel R:R, quel suiveur ? Mesuré, pas décidé.

LE PIÈGE QUE CE BANC ÉVITE. On ne peut PAS reconstruire « et si j'avais pris à 3R ? »
depuis les MFE/MAE du journal : on sait qu'un trade est monté à +3R et descendu à −1R,
mais PAS DANS QUEL ORDRE. La plupart des analyses de « R:R optimal » se trompent là.
La seule méthode exacte est de rejouer le backtest avec d'autres paramètres — ce que
fait ce banc, et rien d'autre.

CE QU'IL Y A À COMPRENDRE AVANT DE LIRE LE TABLEAU. La configuration de production vise
`rr = 6` fois le stop de 4 ATR, soit +24 ATR, avec un suiveur à 5 ATR. Le suiveur mord
donc presque toujours AVANT la cible : le 6:1 nominal n'existe pas dans les faits, et
c'est le couple (cible, suiveur) qui décide, jamais la cible seule. D'où deux balayages
séparés, chacun à l'autre paramètre figé.

Et le seuil de rentabilité n'est pas un choix : à un taux de réussite p, il faut un
payoff supérieur à (1−p)/p. Élargir la cible fait baisser p — les deux bougent ensemble,
et seul le rejeu tranche.

    python scripts/sortie_lab.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

RR = [2.0, 4.0, 6.0, 9.0]        # cible = rr × stop (4 ATR) ; production = 6
TRAILS = [0.0, 3.0, 5.0, 8.0]    # suiveur ATR ; 0 = aucun ; production = 5
RR_PROD, TRAIL_PROD, RISQUE_PROD = 6.0, 5.0, 0.005


def _mesure(data, acmap, vix, n_essais, rr: float, trail: float) -> dict:
    from packages.backtest.fast_swing import fast_swing_backtest
    from packages.execution.costs import CostModel
    from packages.portfolio import fragilite as F
    from scripts.candidats_lab import _stats
    from scripts.sizing_lab import _rendements

    _, journal, equity, _ = fast_swing_backtest(
        data, cash=10_000, costs=CostModel(), asset_classes=acmap,
        target_annual_vol=0.30, max_capital_frac=0.15, max_positions=20, max_pct=0.20,
        atr_stop=4.0, rr=rr, vix=vix, close_at_end=False,
        daily_max_loss=0.06, trail_atr=trail, next_open_fills=True,
        risque_par_trade=RISQUE_PROD)
    trades = [t for t in journal.all() if t.pnl_net is not None]
    trades.sort(key=lambda t: t.exit_ts or t.entry_ts)
    pnls = [t.pnl_net for t in trades]
    duree = [(t.exit_ts - t.entry_ts).days
             for t in trades if t.exit_ts and t.entry_ts]
    return {"n": len(pnls), "net": sum(pnls),
            "jours": (sum(duree) / len(duree)) if duree else 0.0,
            **F.marge_de_payoff(pnls), **F.concentration(pnls),
            **_stats(_rendements(equity), n_essais)}


def _ligne(nom: str, m: dict) -> str:
    esp = m["net"] / m["n"] if m["n"] else 0.0
    return (f"  {nom:>14} | {m['n']:>5} | {m.get('payoff', 0):>6.2f} "
            f"| {m.get('marge_payoff_pct', 0):>6.1f}% | {m.get('jours', 0):>5.0f} "
            f"| {m.get('sharpe', 0):>6.2f} | {m.get('dsr', 0) or 0:>5.1%} "
            f"| {esp:>7.1f} | {m['net']:>9,.0f}")


def _table(titre: str, data, acmap, vix, n_essais, variantes) -> None:
    print(f"\n{titre}")
    cols = ("réglage", "trades", "payoff", "marge", "jours", "Sharpe", "DSR",
            "esp./tr", "net $")
    larg = (14, 5, 6, 7, 5, 6, 5, 7, 9)
    print("  " + " | ".join(f"{c:>{w}}" for c, w in zip(cols, larg, strict=True)))
    print("  " + "-" * 84)
    for nom, rr, trail in variantes:
        print(_ligne(nom, _mesure(data, acmap, vix, n_essais, rr, trail)))


def main() -> None:
    from scripts.sizing_lab import _donnees, _essais, _vix
    data, acmap, mode, n_reels, debut, fin = _donnees()
    if n_reels < 30:
        print("⚠️  Aucune base réelle branchée — ce banc ne décide de rien.")
        return
    vix = _vix(data, debut, fin)
    n_essais = _essais(len(RR) + len(TRAILS))
    print(f"\ndonnées : {len(data)} symboles · mode {mode} · "
          f"risque {RISQUE_PROD:.1%} par trade")

    _table(f"CIBLE (rr × stop 4 ATR), suiveur figé à {TRAIL_PROD:.0f} ATR",
           data, acmap, vix, n_essais,
           [(f"rr {r:.0f}" + (" ◀ prod" if r == RR_PROD else ""), r, TRAIL_PROD)
            for r in RR])
    _table(f"SUIVEUR (ATR), cible figée à rr {RR_PROD:.0f}",
           data, acmap, vix, n_essais,
           [(("sans suiveur" if t == 0 else f"trail {t:.0f}")
             + (" ◀ prod" if t == TRAIL_PROD else ""), RR_PROD, t) for t in TRAILS])

    print("\n  « marge » = de combien le payoff dépasse le seuil (1−p)/p imposé par le")
    print("  taux de réussite. Un payoff ne se lit JAMAIS seul : à 31 % de réussite il")
    print("  faut 2,24 pour ne rien gagner. « jours » = durée moyenne de détention.")
    print("  Élargir la cible monte le payoff ET baisse le taux de réussite : c'est la")
    print("  marge qui arbitre, pas le payoff.\n")


if __name__ == "__main__":
    main()
