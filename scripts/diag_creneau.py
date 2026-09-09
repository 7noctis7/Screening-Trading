"""À quelle heure exécuter le rebalancement ? — décomposer nuit et séance.

  python scripts/diag_creneau.py            # lecture seule, n'écrit rien

DEUX QUESTIONS QU'ON CONFOND. « Quel créneau ? » en cache deux, et elles n'ont pas la
même réponse.

  · LE COÛT. Là-dessus, la pratique de marché est stable et ne demande aucune mesure :
    les trente premières minutes concentrent l'écart achat-vente le plus large et la
    volatilité la plus forte ; la fin de séance concentre la liquidité. Un carnet
    rebalancé une fois par jour s'exécute donc près de la clôture, jamais à l'ouverture.
  · LE RENDEMENT. Là-dessus, aucune règle générale ne vaut : cela dépend de TON univers,
    et cela se mesure. C'est l'objet de ce script.

CE QU'IL MESURE. Chaque séance se coupe en deux morceaux disjoints dont le produit
redonne le rendement de clôture à clôture : la NUIT (clôture veille → ouverture) et la
SÉANCE (ouverture → clôture). Détenir à la clôture capture la nuit ; détenir pendant la
journée capture la séance. Savoir lequel des deux porte le rendement historique de ton
univers dit à quelle heure il faut être en position.

CE QU'IL NE DIT PAS. Aucune stratégie. Capturer la seule nuit imposerait deux
allers-retours par jour, dont le coût dépasserait très probablement le gain — et ce coût
n'est pas mesuré ici. Le résultat éclaire l'HEURE d'un rebalancement quotidien existant,
il ne propose pas d'en faire deux.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from packages.common.device import activer_cudf, banniere  # noqa: E402

activer_cudf()
banniere()

import numpy as np  # noqa: E402

from packages.research.creneau import coherence, decomposer  # noqa: E402

SEUIL_INCOHERENCE = 0.01     # au-delà d'1 % d'observations hors fourchette, on se tait


def _ligne(nom: str, d: dict) -> str:
    if not d.get("available"):
        return f"  {nom:12s} {'—':>10s}"
    part = d["part_nuit"]
    part_txt = "—" if part != part else f"{100 * part:>5.0f}%"
    return (f"  {nom:12s} {d['n_actifs']:>5d} actifs  nuit {100 * d['nuit']:>8.1f}%  "
            f"séance {100 * d['journee']:>8.1f}%  total {100 * d['total']:>8.1f}%  "
            f"part nuit {part_txt}")


def _conclure(global_: dict) -> None:
    if not global_.get("available"):
        return
    part = global_["part_nuit"]
    if part != part:
        print("\n  Rendement total nul : la part de la nuit n'a pas de sens ici.")
        return
    print("\n  CE QUE ÇA VEUT DIRE POUR L'HEURE DU REBALANCEMENT")
    if part > 0.6:
        print("  La majorité du rendement s'est faite PENDANT LA NUIT, marché fermé —")
        print("  donc acquise à qui détenait À LA CLÔTURE. Exécuter en fin de séance")
        print("  cumule alors les deux avantages : la liquidité la plus profonde du")
        print("  jour, et la position en portefeuille au moment où le rendement tombe.")
    elif part < 0.2:
        print("  Le rendement s'est fait PENDANT LA SÉANCE. Être en position dès")
        print("  l'ouverture compte donc plus qu'ici ; c'est le seul cas où exécuter")
        print("  tôt se défend malgré des écarts achat-vente plus larges. À arbitrer")
        print("  contre le surcoût, que ce script ne mesure pas (`make slippage`).")
    else:
        print("  Le rendement se partage entre la nuit et la séance : rien dans TES")
        print("  données ne départage les deux créneaux. Le coût d'exécution devient")
        print("  alors le seul critère, et il désigne la fin de séance.")
    print("\n  Ces chiffres ignorent frais et écarts achat-vente. Ils disent QUAND le")
    print("  rendement tombe, pas ce qu'il en reste après exécution.")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--jours", type=int, default=1500)
    a = ap.parse_args()

    from scripts.valider_nouveautes import charger_panel
    champs, symboles, mode, classes, dates = charger_panel(a.jours)
    o, h, b, c = (champs[k] for k in ("open", "high", "low", "close"))
    print(f"\nPanneau RÉEL : {c.shape[0]} dates × {c.shape[1]} actifs "
          f"(source : {mode})")
    if dates:
        print(f"Période : {str(dates[0])[:10]} → {str(dates[-1])[:10]}")

    part_dehors = coherence(o, h, b, c)
    print(f"\nCohérence OHLC : {100 * part_dehors:.3f} % hors fourchette [bas, haut]")
    if part_dehors > SEUIL_INCOHERENCE:
        print("⛔ Au-delà du seuil : ouverture et clôture n'ont pas la même base")
        print("   d'ajustement. La décomposition nuit/séance serait un artefact de")
        print("   splits et de dividendes — on ne la publie pas. UNCALIBRATED.")
        return
    print("   (sous le seuil : même base pour les quatre colonnes, on décompose)")

    print(f"\n  {'périmètre':12s} {'':>5s}          {'NUIT':^14s} {'SÉANCE':^16s}")
    total = decomposer(o, c)
    print(_ligne("TOUT", total))
    for classe in sorted(set(classes)):
        masque = np.array([x == classe for x in classes])
        print(_ligne(classe, decomposer(o, c, masque)))
    _conclure(total)


if __name__ == "__main__":
    main()
