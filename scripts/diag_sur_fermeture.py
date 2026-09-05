#!/usr/bin/env python3
"""De quoi est fait l'écart quand le COURTIER détient ce que le journal ignore ?

Cf. `packages/research/sur_fermeture.py` pour l'identité complète. En deux lignes :

    manque_ouvert = achats_non_journalises + sur_fermeture

Un achat non journalisé est un TROU (le journal n'a pas le prix de revient d'une
position réelle). Une sur-fermeture est une INVENTION (le journal a soldé des unités
que le courtier n'a jamais vendues, donc produit du « réalisé » sans contrepartie).
La seconde contamine les statistiques ; la première les rend seulement incomplètes.

LECTURE SEULE — ce script ne modifie rien.

    python scripts/diag_sur_fermeture.py                 # tous les symboles concernés
    python scripts/diag_sur_fermeture.py --symbole AVAX   # un seul, ordre par ordre
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SEUIL = 1e-6                       # en deçà, l'écart est du bruit de flottant


def _est_vente(o: dict) -> bool:
    return str(o.get("side", "")).lower() == "sell"


def _ordres() -> list[dict]:
    """Fills réels du courtier. Indisponible ⇒ [] et le motif DIT, jamais une trace
    d'appel : un diagnostic qui plante sur une dépendance absente ressemble à un
    diagnostic cassé."""
    try:
        from packages.execution.alpaca_broker import AlpacaBroker
        o = AlpacaBroker().orders(limit=5000)
    except Exception as e:  # noqa: BLE001 — SDK, clés ou réseau absents
        print(f"  Courtier illisible ({str(e)[:70]}).")
        return []
    print(f"  {len(o)} ordre(s) exécuté(s) chez le courtier, "
          f"dont {sum(1 for x in o if _est_vente(x))} vente(s).")
    return o


def _bloc_symboles(ecarts, cible: str | None) -> None:
    """`invente` et `vente n.j.` sont deux colonnes SÉPARÉES, jamais une seule colonne
    signée : les confondre a fait lire une vraie absence de clôtures comme une preuve
    d'absence de problème (05/09, PATH/NWL sur le VPS). Elles ne sont JAMAIS toutes deux
    non nulles pour un même symbole — `sur_fermeture` n'a qu'un signe à la fois."""
    print("\n  DÉCOMPOSITION DU MANQUE — le courtier porte-t-il plus que le "
          "journal ?\n")
    print(f"    {'symbole':<10}{'attendu':>12}{'ouvert jrn':>12}{'MANQUE':>12}"
          f"{'achats n.j.':>13}{'invente':>10}{'vente n.j.':>12}  identité")
    print("    " + "-" * 93)
    vus = 0
    for e in ecarts:
        if abs(e.manque_ouvert) < SEUIL and abs(e.sur_fermeture) < SEUIL:
            continue
        if cible and e.symbole != cible:
            continue
        vus += 1
        print(f"    {e.symbole:<10}{e.detenu_attendu:>12.4f}{e.ouvert_journal:>12.4f}"
              f"{e.manque_ouvert:>+12.4f}{e.achats_non_journalises:>+13.4f}"
              f"{e.invente:>10.4f}{e.vente_non_journalisee:>12.4f}  "
              f"{'✓' if e.identite_verifiee() else '⚠ NE SE REFERME PAS'}")
    if not vus:
        print("    aucun écart — le journal et le courtier disent la même chose.")
        return
    inv = sum(e.invente for e in ecarts)
    vnj = sum(e.vente_non_journalisee for e in ecarts)
    anj = sum(e.achats_non_journalises for e in ecarts if e.achats_non_journalises > 0)
    print(f"\n    INVENTÉ (grave, contamine les stats)      : {inv:+.4f} unité(s)")
    print(f"    ventes RÉELLES jamais closes au journal    : {vnj:+.4f} unité(s)")
    print(f"    achats RÉELS jamais journalisés            : {anj:+.4f} unité(s)")
    print("    Une identité qui ne se referme pas accuse CE script, pas la donnée.")


def _bloc_ordres(ecarts) -> None:
    exces = [e for e in ecarts if e.surferme]
    print(f"\n  ORDRE PAR ORDRE — {len(ecarts)} vente(s) citée(s) par le journal, "
          f"{len(exces)} en excès\n")
    if not exces:
        print("    Aucune vente ne ferme plus que sa quantité réelle.")
        print("    (Plusieurs lots pour une même vente est NORMAL : le pool FIFO par")
        print("     symbole regroupe les chaînes `P-` et `C-`. Cf. le faux P0 LINK.)")
        return
    for e in exces:
        print(f"    {e.symbole:<10} ordre {e.ordre[:8]} · vendu RÉEL "
              f"{e.vendu_reel:.6f} "
              f"· fermé au journal {e.ferme_journal:.6f} → EXCÈS {e.exces:+.6f}")
        for lot in e.lots:
            print(f"        {lot}")


def main() -> None:
    print(__doc__.split("    python")[0].rstrip())
    cible = None
    if "--symbole" in sys.argv:
        cible = sys.argv[sys.argv.index("--symbole") + 1].upper()
    from packages.research.sur_fermeture import par_ordre, par_symbole
    from packages.storage import SqliteTradeJournal
    trades = SqliteTradeJournal().all()          # legacy COMPRIS : le compte les subit
    print(f"\n  {len(trades)} enregistrement(s) au journal (legacy compris).")
    ordres = _ordres()
    if not ordres:
        print("\n  Aucun ordre lu chez le courtier — clés absentes ou API muette.")
        print("  UNCALIBRATED : sans les fills réels, aucune décomposition "
              "n'est possible.")
        return
    _bloc_symboles(par_symbole(trades, ordres), cible)
    ords = par_ordre(trades, ordres)
    _bloc_ordres([e for e in ords if not cible or e.symbole == cible])


if __name__ == "__main__":
    main()
