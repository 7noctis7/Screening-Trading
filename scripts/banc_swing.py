#!/usr/bin/env python3
"""make banc-swing — le moteur swing ICT vaut-il d'être branché ? On mesure d'abord.

CE QUE CE BANC TRANCHE. `strategies/moteur_swing` (1 374 lignes avec ses
dépendances) n'a aucun appelant. Le brancher changerait ce que le robot achète et
vend ; le supprimer jetterait un travail spécifié. Aucune des deux décisions ne se
prend sans chiffres, et il n'y en avait aucun. Ce script en produit — sur
l'historique RÉEL, jamais synthétique.

CE QU'IL NE FAIT PAS. Il ne branche rien et n'écrit rien au journal. Il lit, simule,
et passe le résultat à `research/gate.verdict_hors_echantillon` — la porte dont le
nombre d'essais est COMPTÉ au ledger, pas choisi par l'appelant.

  make banc-swing                 # actions de l'univers, historique complet
  make banc-swing ARGS="--n 40"   # limite le nombre d'actifs (plus rapide)
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

MIN_BARRES = 200          # sous ce seuil, l'actif n'offre pas de fenêtre exploitable


def _univers(limite: int) -> list[str]:
    from apps.api.snapshot import _db_full_universe
    uni = _db_full_universe() or []
    actions = [r["symbol"] for r in uni if (r.get("asset_class") or "") == "equity"]
    return sorted(actions)[:limite] if limite else sorted(actions)


def _barres(symbole: str):
    from datetime import date, timedelta

    from apps.api.snapshot import _price_db_path
    from packages.data.providers.db_provider import DBPriceProvider
    chemin = _price_db_path()
    if chemin is None:
        return []
    try:
        return DBPriceProvider(chemin).fetch_ohlcv(
            symbole, "1d", date.today() - timedelta(days=4015), date.today())
    except Exception:  # noqa: BLE001
        return []


def _verdict(b: dict) -> None:
    """Le bilan passe-t-il la porte ? DSR déflaté du nombre d'essais RÉEL."""
    from packages.research.gate import verdict_hors_echantillon
    if not b.get("sharpe_par_trade"):
        print("\n  Porte non applicable : pas de Sharpe par trade (dispersion nulle "
              "ou aucun trade).")
        return
    v = verdict_hors_echantillon(sharpe_oos=b["sharpe_par_trade"], n_obs_oos=b["n"])
    print(f"\n  PORTE DE DÉPLOIEMENT — {v['n_essais']} essai(s) comptés au ledger")
    print(f"    DSR             : {v['dsr_calcule']}")
    print(f"    déployable      : {'OUI' if v['deployable'] else 'NON'}")
    for r in v["reasons"]:
        print(f"    · {r}")


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Banc de mesure du moteur swing ICT")
    ap.add_argument("--n", type=int, default=0, help="nb max d'actifs (0 = tous)")
    ap.add_argument("--horizon", type=int, default=40, help="barres avant abandon")
    a = ap.parse_args()

    from packages.backtest.banc_swing import bilan, parcourir
    from packages.strategies.moteur_swing import MarketStructureEngine

    symboles = _univers(a.n)
    if not symboles:
        print("⛔ Aucun univers lisible. La base de prix est-elle en place ?")
        print("   Diagnostic : python -c \"from apps.api.snapshot import "
              "_price_db_path; print(_price_db_path())\"")
        return 1

    moteur = MarketStructureEngine()
    tous, couverts, ignores = [], 0, 0
    print(f"\nBanc swing ICT · {len(symboles)} actif(s) candidats\n")
    for s in symboles:
        barres = _barres(s)
        if len(barres) < MIN_BARRES:
            ignores += 1
            continue
        couverts += 1
        tous.extend(parcourir(s, barres, moteur.detecter, horizon=a.horizon))

    print(f"  {couverts} actif(s) mesurés · {ignores} écarté(s) "
          f"(< {MIN_BARRES} barres)")
    b = bilan(tous)
    if not b["n"]:
        print(f"\n  {b['statut']} — le moteur n'a produit AUCUN trade exécutable.")
        print("  Ce n'est pas un échec du banc : c'est un résultat. Un signal")
        print("  qui ne se remplit jamais ne se branche pas non plus.")
        return 0
    print(f"\n  {b['n']} trade(s)")
    print(f"    espérance       : {b['esperance_r']:+.3f} R par trade")
    print(f"    taux de réussite: {b['taux_reussite']:.1%}")
    print(f"    total           : {b['total_r']:+.1f} R")
    print(f"    Sharpe/trade    : {b['sharpe_par_trade']}")
    print(f"    sorties         : {b['par_sortie']}")
    _verdict(b)
    print("\n  RIEN N'A ÉTÉ BRANCHÉ. Ce banc mesure ; brancher reste une décision.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
