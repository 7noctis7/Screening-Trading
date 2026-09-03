#!/usr/bin/env python3
"""Ferme les lots ORPHELINS du journal avec les fills RÉELS du courtier.

CE QUE CE SCRIPT RÉPARE. Mesuré le 03/09 : le journal portait ~80 actions que le
compte ne détient plus, deux fois trop de QQQ, et sa poche crypto sous une convention
de nommage que les ventes n'ont jamais pu apparier. Conséquence mécanique : les ventes
RÉCENTES se sont appariées en FIFO à ces lots morts, produisant 5 821 $ de « réalisé »
là où le compte n'avait gagné que 876 $.

POURQUOI ON NE BASCULE PAS CES LOTS EN `legacy=1`. Ce serait le geste rapide, et il
serait faux : `legacy=1` signifie « fill importé sans features de décision ». Ces
lots-là ne sont pas ça — ce sont des lots dont la SORTIE n'a jamais été enregistrée.
Réutiliser un drapeau pour un second sens le rend illisible : dans six mois, personne
ne saura pourquoi ces lots sont legacy, ni ce qu'on croyait au moment de les marquer.

CE QU'ON FAIT À LA PLACE, ET C'EST LA PRATIQUE COMPTABLE ORDINAIRE : on ne supprime ni
ne réécrit un enregistrement, on POSTE UNE ÉCRITURE DE CORRECTION, datée, avec son
motif et sa source. Ici la source est la meilleure possible — l'historique des ordres
exécutés chez le courtier. Chaque fermeture porte donc le prix et la DATE du fill
réel, pas ceux du jour où l'on répare.

CE QU'ON NE FAIT PAS. Un lot dont aucune vente ne rend compte reste OUVERT et est
signalé. Le fermer « au dernier prix connu » fabriquerait un P&L qui n'a jamais existé
— exactement l'erreur qu'on est en train de corriger.

    python scripts/reconcilier_journal.py              # SIMULATION (par défaut)
    python scripts/reconcilier_journal.py --appliquer  # écrit, après sauvegarde
"""

from __future__ import annotations

import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

LIMITE_ORDRES = 500          # profondeur d'historique demandée au courtier
MOTIF = "reconciliation-journal"


def _canon(s: str) -> str:
    from packages.research.biais_fermeture import symbole_canonique
    return symbole_canonique(s)


def _ventes_courtier(limite: int = LIMITE_ORDRES) -> list[dict]:
    """Ventes RÉELLEMENT exécutées, telles que le courtier les rapporte.

    Seule source admissible : ni le snapshot ni une reconstruction à partir des
    positions actuelles ne disent à quel prix ni à quelle date une vente a eu lieu.
    """
    try:
        from packages.execution.alpaca_broker import AlpacaBroker
        ordres = AlpacaBroker().orders(limit=limite)
    except Exception as e:  # noqa: BLE001
        print(f"  Courtier injoignable ({str(e)[:70]}) — rien ne peut être réparé "
              "sans sa vérité. Aucune écriture.")
        return []
    return [o for o in ordres
            if o.get("side") == "sell" and float(o.get("price") or 0) > 0]


def _lots_ouverts(journal) -> list:
    return sorted((t for t in journal.all() if t.exit_ts is None),
                  key=lambda t: t.entry_ts)


def _plan(lots: list, ventes: list[dict]) -> tuple[list, list]:
    """Appariement FIFO des ventes aux lots, PAR SYMBOLE CANONIQUE. Aucune écriture.

    Renvoie (fermetures proposées, lots restés orphelins). Séparer le plan de son
    application est ce qui permet de le RELIRE avant de toucher au registre.
    """
    restants: dict[str, list] = {}
    for lot in lots:
        restants.setdefault(_canon(lot.instrument), []).append(lot)
    fermetures = []
    for v in sorted(ventes, key=lambda x: x.get("date") or ""):
        pool = restants.get(_canon(v["symbol"]), [])
        a_placer = float(v["qty"])
        while a_placer > 1e-9 and pool:
            lot = pool[0]
            prise = min(float(lot.qty), a_placer)
            fermetures.append({"lot": lot, "qty": prise, "prix": float(v["price"]),
                               "date": v.get("date", ""), "symbole_vente": v["symbol"]})
            a_placer -= prise
            if prise >= float(lot.qty) - 1e-9:
                pool.pop(0)
            else:
                pool[0] = _reduire(lot, prise)
    fermes = {id(f["lot"]) for f in fermetures}
    orphelins = [x for x in lots if id(x) not in fermes]
    return fermetures, orphelins


def _reduire(lot, prise: float):
    import dataclasses
    return dataclasses.replace(lot, qty=round(float(lot.qty) - prise, 10))


def _resume(fermetures: list, orphelins: list, lots: list) -> None:
    print(f"\n  PLAN — {len(fermetures)} fermeture(s) appariée(s) à un fill réel, "
          f"{len(orphelins)} lot(s) sans vente correspondante (sur {len(lots)})\n")
    if fermetures:
        gains = 0.0
        for f in fermetures[:15]:
            lot = f["lot"]
            pnl = (f["prix"] - float(lot.entry_price)) * f["qty"]
            gains += pnl
            print(f"    {lot.instrument:<12} {f['qty']:>12.6f} @ {f['prix']:>10.4f} "
                  f"le {f['date'][:10]}  → {pnl:+10.2f} $")
        if len(fermetures) > 15:
            print(f"    … et {len(fermetures) - 15} autres")
        total = sum((f["prix"] - float(f["lot"].entry_price)) * f["qty"]
                    for f in fermetures)
        print(f"\n    P&L des fermetures proposées : {total:+,.2f} $")
    if orphelins:
        dates = sorted(str(t.entry_ts)[:10] for t in orphelins)
        print(f"\n    {len(orphelins)} lots RESTENT OUVERTS")
        print(f"    (entrés entre {dates[0]} et {dates[-1]})")
        print("    Aucune vente du courtier n'en rend compte : les fermer reviendrait")
        print("    à inventer un prix et une date. Ils restent tels quels, et la")
        print("    réconciliation du panneau continuera de signaler l'écart.")


def _appliquer(journal, fermetures: list) -> int:
    """Écrit les fermetures. Chaque écriture porte la DATE du fill et son motif."""
    import dataclasses

    from packages.execution.live_roundtrip import _close_record
    n = 0
    for f in fermetures:
        lot, q = f["lot"], f["qty"]
        try:
            ts = datetime.fromisoformat(f["date"])
        except (TypeError, ValueError):
            continue                                  # date illisible → on ne ferme pas
        total = float(lot.qty)
        if q >= total - 1e-9:
            rec = _close_record(lot, total, f["prix"], ts, None)
        else:
            rec = _close_record(lot, q, f["prix"], ts, None, split_id=f"{lot.id}-R1")
            journal.append(dataclasses.replace(lot, qty=round(total - q, 10)),
                           legacy=False)
        journal.append(dataclasses.replace(rec, exit_reason=MOTIF), legacy=False)
        n += 1
    return n


def main() -> None:
    print(__doc__.split("    python")[0].rstrip())
    appliquer = "--appliquer" in sys.argv
    from packages.storage import SqliteTradeJournal
    journal = SqliteTradeJournal()
    lots = _lots_ouverts(journal)
    if not lots:
        print("\n  Aucun lot ouvert — rien à réconcilier.")
        return
    ventes = _ventes_courtier()
    if not ventes:
        return
    print(f"\n  {len(ventes)} vente(s) réelle(s) récupérée(s) chez le courtier.")
    fermetures, orphelins = _plan(lots, ventes)
    _resume(fermetures, orphelins, lots)
    if not appliquer:
        print("\n  SIMULATION — rien n'a été écrit. Relancer avec `--appliquer` pour "
              "poster\n  les écritures de correction (une sauvegarde du journal est "
              "faite avant).")
        return
    src = ROOT / "data" / "journal.db"
    if src.exists():
        horo = f"{datetime.now():%Y%m%d-%H%M%S}"
        dest = src.with_suffix(f".avant-reconciliation-{horo}.db")
        shutil.copy2(src, dest)
        print(f"\n  Sauvegarde : {dest.name}")
    n = _appliquer(journal, fermetures)
    print(f"  {n} écriture(s) de correction postée(s), au prix et à la date des fills "
          "réels.")
    print("  Relancer `make diag-journal` pour vérifier que l'écart s'est refermé.")


if __name__ == "__main__":
    main()
