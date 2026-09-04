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
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

LIMITE_ORDRES = 5000         # profondeur demandée ; l'API pagine par 500
MOTIF = "reconciliation-journal"

# IDEMPOTENCE. Chaque fermeture porte l'IDENTIFIANT du fill qui l'a produite, et un
# fill déjà consommé n'est jamais rejoué. Sans cela l'outil n'est pas rejouable : au
# deuxième passage il réapplique TOUT l'historique de ventes aux lots encore ouverts,
# et finit par fermer des lots qu'aucune vente ne couvre. Constaté le 03/09 — le second
# plan proposait 50 fermetures de plus, toutes à +0,00 $, sur les mêmes 202 ventes.


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
    ventes = [o for o in ordres
              if o.get("side") == "sell" and float(o.get("price") or 0) > 0]
    print(f"\n  {len(ordres)} ordre(s) exécuté(s) récupéré(s), dont {len(ventes)} "
          f"vente(s).")
    if len(ordres) >= limite:
        print("  ⚠️ Le plafond demandé est ATTEINT : l'historique est peut-être encore "
              "tronqué.\n     Relancer avec une limite plus haute avant de conclure.")
    return ventes


def _lots_ouverts(journal) -> tuple[list, set]:
    """Lots ouverts (TOUS périmètres) + l'ensemble des ids NON legacy.

    Le drapeau doit voyager avec le lot. Sans lui, la fermeture d'un lot importé
    ressortirait en `legacy=0`, c'est-à-dire DANS les statistiques affichées — et sans
    features de décision, puisqu'un fill importé n'en a jamais eu. On réparerait le
    registre en polluant précisément le chiffre qu'on cherche à assainir.
    """
    ids_vivants = {t.id for t in journal.all(legacy=False)}
    lots = sorted((t for t in journal.all() if t.exit_ts is None),
                  key=lambda t: t.entry_ts)
    return lots, ids_vivants


def _ventes_deja_consommees(journal) -> dict[str, float]:
    """QUANTITÉ déjà consommée par fill de vente — pas seulement la liste des ids.

    Écarter un fill dès qu'il a servi UNE FOIS était trop grossier. Une vente de 500
    unités qui n'avait trouvé que 200 unités de lots (les autres achats n'étant pas
    journalisés) était marquée consommée en entier : ses 300 unités restantes ne
    pouvaient plus jamais fermer les lots reconstitués ensuite par
    `completer_ouvertures`, qui seraient restés ouverts pour toujours.

    Compter la quantité, et non l'identifiant, rejoue exactement le RESTE d'un fill —
    ni plus (pas de réalisé fabriqué), ni moins (pas de lot condamné à rester ouvert).
    """
    prefixe = MOTIF + ":"
    consomme: dict[str, float] = {}
    for t in journal.all():
        motif = t.exit_reason or ""
        if not motif.startswith(prefixe):
            continue
        cle = motif[len(prefixe):]
        consomme[cle] = consomme.get(cle, 0.0) + float(t.qty or 0.0)
    return consomme


def _restant(ventes: list[dict], consomme: dict[str, float]) -> list[dict]:
    """Ventes amputées de ce qu'elles ont déjà fermé. Une vente épuisée disparaît."""
    out = []
    for v in ventes:
        deja = consomme.get(str(v.get("id") or ""), 0.0)
        reste = float(v["qty"]) - deja
        if reste > 1e-9:
            out.append({**v, "qty": reste})
    return out


def _fermetures_sans_identite(journal) -> int:
    """Fermetures écrites AVANT l'idempotence : motif nu, sans identifiant de vente.

    Elles sont intraçables : impossible de savoir quelles ventes elles ont consommées,
    donc impossible de garantir qu'un nouveau passage ne les rejouera pas. Le seul geste
    sûr est de REFUSER de tourner et de renvoyer à une sauvegarde — deviner ici
    reviendrait à fabriquer du réalisé, ce que cet outil existe pour empêcher.
    """
    return sum(1 for t in journal.all() if (t.exit_reason or "") == MOTIF)


def _anterieur(lot, vente: dict) -> bool:
    """Le lot existait-il DÉJÀ quand la vente a eu lieu ?

    CORRECTIF (03/09, signalé sur le compte réel : DUOL affichait une entrée au 03/09
    et une sortie au 01/09). L'appariement prenait le plus ancien lot du symbole sans
    jamais regarder sa date d'entrée. Une vente pouvait donc fermer un lot qui n'existait
    pas encore — et le round-trip fabriqué portait un P&L calculé sur un prix de revient
    postérieur à la sortie. Une sortie ne peut pas précéder son entrée : c'est vrai avant
    toute considération de FIFO, et ça se vérifie sur deux dates.

    Comparaison au JOUR, pas à la seconde. Un achat suivi d'une vente le même jour est
    légitime, et l'heure des deux sources n'est pas comparable : le lot porte l'instant
    où le run l'a écrit, le fill porte celui de l'exécution. Trancher à la seconde
    refuserait des aller-retours réels.

    Date illisible d'un côté ou de l'autre → on REFUSE plutôt que de supposer valide.
    """
    d_vente = _horodatage(vente.get("date"))
    d_lot = _horodatage(lot.entry_ts)
    if d_vente is None or d_lot is None:
        return False
    return d_lot.date() <= d_vente.date()


def _plan(lots: list, ventes: list[dict]) -> tuple[list, list]:
    """Appariement FIFO des ventes aux lots, PAR SYMBOLE CANONIQUE. Aucune écriture.

    Le FIFO ne s'applique QU'AUX lots antérieurs à la vente (`_anterieur`) : un lot plus
    récent que la vente est sauté, jamais fermé par elle.

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
        i = 0
        while a_placer > 1e-9 and i < len(pool):
            if not _anterieur(pool[i], v):
                i += 1                        # lot postérieur à la vente : on le saute
                continue
            lot = pool[i]
            prise = min(float(lot.qty), a_placer)
            fermetures.append({"lot": lot, "qty": prise, "prix": float(v["price"]),
                               "date": v.get("date", ""), "symbole_vente": v["symbol"],
                               "id_vente": str(v.get("id") or "")})
            a_placer -= prise
            if prise >= float(lot.qty) - 1e-9:
                pool.pop(i)
            else:
                pool[i] = _reduire(lot, prise)
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


def _horodatage(brut) -> datetime | None:
    """Date de fill en UTC AWARE, ou `None` si illisible.

    Les dates du courtier portent un fuseau, mais rien ne le garantit : une date nue
    (« 2026-08-15 ») produit un datetime NAÏF, et le soustraire à une entrée aware lève
    une TypeError EN PLEINE ÉCRITURE — donc après que des enregistrements ont déjà été
    commités. Une réparation de registre ne doit jamais s'arrêter à mi-chemin.
    """
    try:
        ts = datetime.fromisoformat(str(brut))
    except (TypeError, ValueError):
        return None
    return ts if ts.tzinfo else ts.replace(tzinfo=UTC)


def _appliquer(journal, fermetures: list, ids_vivants: set) -> int:
    """Écrit les fermetures. Chaque écriture porte la DATE du fill, son motif, et
    CONSERVE le périmètre (`legacy`) du lot d'origine.

    Le suffixe de scission est NUMÉROTÉ par lot : un même lot soldé en plusieurs
    ventes produirait sinon plusieurs enregistrements au même id `-R1`, et l'UPSERT
    ne garderait que le dernier — les fermetures intermédiaires disparaîtraient.
    """
    import dataclasses

    from packages.execution.live_roundtrip import _close_record
    n, compteur = 0, {}
    for f in fermetures:
        lot, q = f["lot"], f["qty"]
        ts = _horodatage(f["date"])
        if ts is None:
            continue                                  # date illisible → on ne ferme pas
        est_vivant = lot.id.split("-R")[0] in ids_vivants
        total = float(lot.qty)
        if q >= total - 1e-9:
            rec = _close_record(lot, total, f["prix"], ts, None)
        else:
            compteur[lot.id] = compteur.get(lot.id, 0) + 1
            rec = _close_record(lot, q, f["prix"], ts, None,
                                split_id=f"{lot.id}-R{compteur[lot.id]}")
            journal.append(dataclasses.replace(lot, qty=round(total - q, 10)),
                           legacy=not est_vivant)
        journal.append(
            dataclasses.replace(rec, exit_reason=f"{MOTIF}:{f.get('id_vente', '')}"),
            legacy=not est_vivant)
        n += 1
    return n


def main() -> None:
    print(__doc__.split("    python")[0].rstrip())
    appliquer = "--appliquer" in sys.argv
    from packages.storage import SqliteTradeJournal
    journal = SqliteTradeJournal()
    orphelines = _fermetures_sans_identite(journal)
    if orphelines:
        print(f"\n  ⛔ ARRÊT — {orphelines} fermeture(s) antérieure(s) ne portent pas")
        print("     l'identifiant de la vente qui les a produites. On ne")
        print("     peut donc pas savoir quelles ventes ont déjà été consommées, ni")
        print("     garantir qu'un nouveau passage ne les rejouera pas — ce qui")
        print("     fabriquerait du réalisé sans contrepartie.")
        print("\n     Restaurer une sauvegarde ANTÉRIEURE à cette réconciliation, puis")
        print("     relancer une seule fois avec cette version :")
        print("       ls -1 data/journal.avant-reconciliation-*.db")
        print("       cp data/journal.avant-reconciliation-<la-plus-ancienne>.db "
              "data/journal.db")
        return
    lots, ids_vivants = _lots_ouverts(journal)
    deja = _ventes_deja_consommees(journal)
    if not lots:
        print("\n  Aucun lot ouvert — rien à réconcilier.")
        return
    ventes = _ventes_courtier()
    if deja:
        avant_n = len(ventes)
        avant_q = sum(float(v["qty"]) for v in ventes)
        ventes = _restant(ventes, deja)
        reste_q = sum(float(v["qty"]) for v in ventes)
        print(f"  {avant_n - len(ventes)} vente(s) ENTIÈREMENT consommée(s) par une "
              f"réconciliation antérieure ;\n  {avant_q - reste_q:,.4f} unité(s) déjà "
              "fermée(s) au total : seul le RESTE est rejoué.".replace(",", " "))
    if not ventes:
        print("\n  Aucune vente nouvelle à apparier — le journal est à jour.")
        return
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
    n = _appliquer(journal, fermetures, ids_vivants)
    print(f"  {n} écriture(s) de correction postée(s), au prix et à la date des fills "
          "réels.")
    print("  Relancer `make diag-journal` pour vérifier que l'écart s'est refermé.")


if __name__ == "__main__":
    main()
