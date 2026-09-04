#!/usr/bin/env python3
"""Un signal candidat dit-il quelque chose de NOUVEAU, ou répète-t-il l'existant ?

POURQUOI CE BANC PASSE AVANT TOUTE IMPLÉMENTATION. Le Sharpe d'une combinaison de N flux
de Sharpe s et de corrélation moyenne rho vaut s·sqrt(N/(1+(N-1)·rho)). Avec le preset
à 0,82, ajouter un flux corrélé à 0,73 rapporte +0,06 — bien sous le plus petit écart
détectable sur 11 ans (±0,27). Autrement dit : un signal, aussi bon soit-il seul, ne
peut rien apporter s'il dit la même chose que celui qu'on a déjà.

D'où l'ordre des opérations : on mesure d'abord le RECOUVREMENT, on construit ensuite.
Dix minutes ici évitent des semaines de câblage inutile.

CE QU'ON COMPARE. Le filtre de production de `fast_swing` — cours > MM50 ET MM50
croissante — contre les concepts de `indicators/market_structure` (structure par
pivots, échec d'enchère, volume exceptionnel). Le coefficient est le PHI de Matthews,
c'est-à-dire la corrélation de Pearson entre deux binaires : il vaut 0 quand les deux
signaux sont indépendants et 1 quand ils sont identiques. Le taux d'accord brut seul
tromperait — deux signaux allumés 80 % du temps « s'accordent » à 68 % par hasard.

    python scripts/signal_lab.py            # ~120 titres, pas de 5 jours
    python scripts/signal_lab.py 300 3      # plus de titres, pas plus fin
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SEUIL_REDONDANT = 0.50           # au-delà, le candidat répète l'existant


def _phi(a: list[bool], b: list[bool]) -> float:
    """Coefficient phi de Matthews : corrélation de Pearson entre deux binaires."""
    n11 = sum(1 for x, y in zip(a, b, strict=True) if x and y)
    n10 = sum(1 for x, y in zip(a, b, strict=True) if x and not y)
    n01 = sum(1 for x, y in zip(a, b, strict=True) if not x and y)
    n00 = sum(1 for x, y in zip(a, b, strict=True) if not x and not y)
    den = math.sqrt((n11 + n10) * (n01 + n00) * (n11 + n01) * (n10 + n00))
    return (n11 * n00 - n10 * n01) / den if den > 0 else 0.0


def _filtre_production(barres, i: int, trend: int = 50, pente: int = 5) -> bool:
    """Le filtre EXACT de `fast_swing` : cours > MM50 et MM50 croissante."""
    if i < trend + pente:
        return False
    mm = sum(float(b.close) for b in barres[i - trend + 1:i + 1]) / trend
    j = i - pente
    mmj = sum(float(b.close) for b in barres[j - trend + 1:j + 1]) / trend
    return float(barres[i].close) > mm and mm > mmj


def _candidats(barres, i: int) -> dict[str, bool]:
    from packages.indicators.market_structure import (
        echec_enchere,
        tendance,
        volume_exceptionnel,
    )
    return {
        "structure haussière (pivots)": tendance(barres, i) == "haussier",
        "échec d'enchère (sweep)": bool(echec_enchere(barres, i).get("echec")),
        "volume exceptionnel": bool(volume_exceptionnel(barres, i)),
    }


def main() -> None:
    from scripts.sizing_lab import _donnees
    n_max = int(sys.argv[1]) if len(sys.argv) > 1 else 120
    pas = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    data, _acmap, mode, n_reels, _d, _f = _donnees()
    if n_reels < 30:
        print("⚠️  Aucune base réelle branchée — ce banc ne décide de rien.")
        return
    syms = sorted(data)[:n_max]
    print(f"\n{len(syms)} titres · mode {mode} · un point tous les {pas} jours\n")

    prod: list[bool] = []
    cand: dict[str, list[bool]] = {}
    for s in syms:
        b = data[s]
        for i in range(60, len(b), pas):
            prod.append(_filtre_production(b, i))
            for nom, v in _candidats(b, i).items():
                cand.setdefault(nom, []).append(v)

    part_prod = sum(prod) / len(prod) if prod else 0.0
    print(f"  {'signal candidat':<32} {'allumé':>8} {'accord':>8} {'phi':>7}  verdict")
    print("  " + "-" * 72)
    print(f"  {'FILTRE DE PRODUCTION':<32} {part_prod:>7.1%} {'—':>8} {'—':>7}")
    for nom, v in cand.items():
        accord = sum(1 for x, y in zip(prod, v, strict=True) if x == y) / len(v)
        phi = _phi(prod, v)
        verdict = ("REDONDANT — ne rien construire"
                   if abs(phi) >= SEUIL_REDONDANT else "distinct → à backtester")
        print(f"  {nom:<32} {sum(v)/len(v):>7.1%} {accord:>7.1%} "
              f"{phi:>+7.2f}  {verdict}")

    print(f"\n  {len(prod):,} observations. phi = corrélation entre binaires :")
    print("  0 = indépendants, 1 = identiques. Le taux d'accord SEUL trompe — deux")
    print("  signaux allumés 80 % du temps s'accordent à 68 % par pur hasard.")
    print(f"  Seuil retenu : |phi| >= {SEUIL_REDONDANT:.2f} → le candidat répète "
          "l'existant, et le\n  tableau de combinaison dit qu'il n'apportera pas "
          "de Sharpe.\n")


if __name__ == "__main__":
    main()
