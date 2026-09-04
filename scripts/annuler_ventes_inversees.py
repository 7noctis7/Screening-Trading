#!/usr/bin/env python3
"""Retire du journal les lots « ouverts » qui sont en réalité des VENTES.

CE QUI A ÉTÉ MESURÉ, ET DANS QUEL ORDRE. La complétion des entrées puis la
réconciliation des sorties ont refermé l'identité comptable (écart +3,93 $ sur
+868,83 $). Ce qui restait était un excédent de QUANTITÉ : 29 symboles portant
jusqu'à deux fois l'achat. Le diagnostic a montré où il vit — pas dans les
fermetures, qui égalent la quantité achetée au dix-millième sur 79 symboles sur
87, mais dans les lots ouverts, dont 33 sur 52 portent le symbole, la quantité et
le prix EXACTS d'une vente exécutée.

CE QU'ON RETIRE, ET SEULEMENT ÇA. Les lots dont la signature est celle d'un fill
de VENTE unique. Une vente exécutée en plusieurs fills n'est pas appariée : son
lot reste ouvert et reste signalé. On préfère un registre encore imparfait à un
registre nettoyé sur une présomption.

CE QU'ON N'A PAS FAIT, ET POURQUOI. Ni écriture de correction, ni fermeture au
prix d'entrée. Fermer produirait un aller-retour à 0,00 $ qui n'a jamais eu lieu
et gonflerait le nombre de trades — on remplacerait une fausse position par un
faux trade. Une opération qui n'a pas eu lieu se retire ; elle ne se corrige pas.

CE QUI SURVIT AU RETRAIT. Une sauvegarde horodatée de la base, ET un fichier JSON
qui garde chaque ligne retirée avec le fill qui l'a désignée. Un retrait sans sa
preuve n'est pas rejugeable, et un registre qu'on ne peut pas rejuger ne vaut pas
mieux que celui qu'on répare.

    python scripts/annuler_ventes_inversees.py              # SIMULATION (défaut)
    python scripts/annuler_ventes_inversees.py --appliquer  # retire, après archive
"""

from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

LIMITE_ORDRES = 5000


def _ordres() -> list[dict]:
    """Ordres exécutés du courtier. Injoignable → aucune preuve, donc aucun retrait."""
    try:
        from packages.execution.alpaca_broker import AlpacaBroker
        return AlpacaBroker().orders(limit=LIMITE_ORDRES)
    except Exception as e:  # noqa: BLE001
        print(f"  Courtier injoignable ({str(e)[:70]}). Sans ses fills, rien ne "
              "désigne un lot : aucun retrait.")
        return []


def _resume(a_annuler: list[dict], n_ouverts: int) -> None:
    print(f"\n  PLAN — {len(a_annuler)} lot(s) « ouvert(s) » sur {n_ouverts} portent "
          "la signature EXACTE d'une vente\n")
    total = 0.0
    for e in sorted(a_annuler, key=lambda x: -float(x["lot"].qty or 0))[:15]:
        t, f = e["lot"], e["fill"]
        total += float(t.qty or 0) * float(t.entry_price or 0)
        print(f"    {t.instrument:<12} {float(t.qty):>13.6f} @ "
              f"{float(t.entry_price):>9.4f}  ← vente du {str(f.get('date'))[:10]}")
    if len(a_annuler) > 15:
        print(f"    … et {len(a_annuler) - 15} autres")
    montant = sum(float(e["lot"].qty or 0) * float(e["lot"].entry_price or 0)
                  for e in a_annuler)
    print(f"\n    Exposition FICTIVE retirée : {montant:,.2f} $".replace(",", " "))
    print("    (ces lots ne sont pas des positions : le compte ne les détient pas)")


def main() -> None:
    print(__doc__.split("    python")[0].rstrip())
    from packages.research.ventes_inversees import (
        archive,
        lots_a_annuler,
        ventes_du_courtier,
    )
    from packages.storage import SqliteTradeJournal
    journal = SqliteTradeJournal()
    ouverts = [t for t in journal.all() if t.exit_ts is None]
    ordres = _ordres()
    if not ordres:
        return
    a_annuler = lots_a_annuler(ouverts, ventes_du_courtier(ordres))
    _resume(a_annuler, len(ouverts))
    if not a_annuler:
        print("\n  Aucun lot ouvert ne porte la signature d'une vente : "
              "rien à retirer.")
        return
    if "--appliquer" not in sys.argv:
        print("\n  SIMULATION — rien n'a été retiré. Relancer avec `--appliquer`.")
        return
    horo = f"{datetime.now():%Y%m%d-%H%M%S}"
    src = ROOT / "data" / "journal.db"
    if src.exists():
        dest = src.with_suffix(f".avant-annulation-{horo}.db")
        shutil.copy2(src, dest)
        print(f"\n  Sauvegarde : {dest.name}")
    piste = ROOT / "data" / f"lots-annules-{horo}.json"
    piste.write_text(json.dumps([archive(e) for e in a_annuler],
                                indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  Archive des lignes retirées, avec leur preuve : {piste.name}")
    n = journal.supprimer([e["lot"].id for e in a_annuler])
    print(f"  {n} lot(s) retiré(s).")
    print("  Relancer `make diag-journal` : l'excédent de quantité doit avoir fondu.")


if __name__ == "__main__":
    main()
