#!/usr/bin/env python3
"""Reconstruire le journal À PARTIR DES SEULS FILLS DU COURTIER.

POURQUOI (18/09). Trois mois de réparations n'ont pas suffi : 167 lots importés dont la
provenance est illisible, 88 lots ouverts qu'aucune vente ne solde, 29 symboles que le
compte ne détient plus, NWL et MAS portant ~2× leur achat. Ces défauts viennent tous
d'écritures produites AILLEURS que chez le courtier, et les refermer demanderait
d'inventer un prix ou une date.

L'historique des ordres exécutés d'Alpaca, lui, contient tout : symbole, sens, quantité,
prix, horodatage, identifiant de fill. Rejoué en FIFO (`packages.research`
`.reconstruction_journal`), il produit mécaniquement les lots ouverts ET les
aller-retours fermés. Ce qui n'y figure pas n'entre pas au registre.

FAIL-CLOSED, ET LA PORTE EST L'INVENTAIRE RÉEL. Le rejeu n'est écrit QUE s'il retombe,
symbole par symbole, sur ce que le courtier détient aujourd'hui. Un registre reconstruit
qui ne colle pas à l'inventaire est faux ; l'écrire quand même, ce serait refaire
exactement l'erreur qu'on corrige.

    python scripts/reconstruire_journal.py              # SIMULATION (défaut)
    python scripts/reconstruire_journal.py --appliquer  # archive, vide, réécrit
"""
from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


# `orders()` PLAFONNE À 100 PAR DÉFAUT, et `paginer` rend `res[:limit]` : le défaut
# n'est pas une taille de page, c'est un TOTAL. Premier passage réel (18/09) : 100 fills
# rendus sur ~800, donc les achats de juin absents, donc deux ventes QQQ « sans lot » et
# un écart de 61 parts. Le script accusait l'historique d'être tronqué — il l'était, par
# son propre appel. Une valeur par défaut commode ailleurs devient un piège ici, où le
# script REFUSE d'écrire sur la foi de ce qu'il a lu.
LIMITE_ORDRES = 5000


def _courtier() -> dict:
    """Fills et positions RÉELS. `lisible=False` si on ne peut pas savoir — et alors on
    n'écrit rien : l'absence de réponse n'est pas une réponse vide."""
    try:
        from packages.execution.alpaca_broker import AlpacaBroker
        b = AlpacaBroker(paper=True)
        pos = {str(p.get("symbol")): float(p.get("qty") or 0.0)
               for p in b.positions_detailed()}
        return {"lisible": True, "fills": b.orders(limit=LIMITE_ORDRES),
                "positions": pos,
                "equity": round(float(b.equity()), 2)}
    except Exception as e:  # noqa: BLE001
        return {"lisible": False, "motif": str(e)[:160]}


def _classe(symbole: str):
    from packages.core.models import AssetClass
    from packages.execution.alpaca_broker import _is_crypto_symbol
    return AssetClass.CRYPTO if _is_crypto_symbol(symbole) else AssetClass.EQUITY


def _record(lot: dict, n: int, ferme: bool):
    """Un lot du rejeu → `TradeRecord`. Le préfixe `R-` DIT la provenance.

    Pas de `features_snapshot` : ces lots viennent du courtier, pas d'une décision, et
    inventer des features rendrait le registre inutilisable pour la calibration ML —
    la confusion exacte que le drapeau `legacy` avait déjà causée.
    """
    from packages.core.models import Side, TradeRecord
    sym = lot["symbole"]
    entree = datetime.fromisoformat(lot["entree_ts"]) if lot["entree_ts"] else None
    sortie = (datetime.fromisoformat(lot["sortie_ts"])
              if ferme and lot.get("sortie_ts") else None)
    return TradeRecord(
        id=f"R-{(entree or datetime.now()).strftime('%Y%m%d')}-Alpaca-{sym}-{n}",
        instrument=sym, asset_class=_classe(sym), venue="Alpaca", side=Side.LONG,
        qty=float(lot["qty"]), entry_ts=entree, entry_price=float(lot["entree_prix"]),
        avg_price=float(lot["entree_prix"]),
        exit_ts=sortie, exit_price=lot.get("sortie_prix"),
        entry_reason=f"fill courtier {lot.get('ordre_entree', '')}"[:120],
        exit_reason=(f"fill courtier {lot.get('ordre_sortie', '')}"[:120]
                     if ferme else ""),
        pnl_net=lot.get("pnl_net"), pnl_gross=lot.get("pnl_net"),
        pnl_pct=lot.get("pnl_pct"),
        is_win=(None if not ferme else bool(float(lot.get("pnl_net") or 0.0) > 0)),
    )


def _rapport(r, c: dict, verdict: dict) -> None:
    print(f"\n  FILLS DU COURTIER — {len(c['fills'])} ordre(s) exécuté(s)")
    print(f"  REJEU FIFO — {len(r.fermes)} aller-retour(s) fermé(s), "
          f"{len(r.ouverts)} lot(s) ouvert(s)")
    print(f"    réalisé reconstruit : {r.realise:+,.2f} $".replace(",", " "))
    if r.ignores:
        print(f"    {len(r.ignores)} fill(s) illisible(s) écarté(s)")
    if r.ventes_orphelines:
        q = sum(v["qty"] for v in r.ventes_orphelines)
        print(f"    ⚠ {len(r.ventes_orphelines)} vente(s) sans lot "
              f"({q:.4f} unité(s)) — historique tronqué :")
        for v in r.ventes_orphelines[:8]:
            print(f"        {v['symbole']:<10} {v['qty']:12.6f} @ {v['prix']:10.4f} "
                  f"le {v['ts'][:10]}")

    print(f"\n  CONFRONTATION À L'INVENTAIRE RÉEL — {verdict['n_symboles']} symbole(s)")
    for f in verdict.get("frais_nature") or []:
        # NOMMÉ, PAS ABSORBÉ. Les `CFEE` d'Alpaca se prélèvent en JETONS et n'entrent
        # pas dans l'historique des ordres : un rejeu d'achats et de ventes surestime
        # donc toujours une quantité crypto. On l'écrit plutôt que de l'arrondir.
        print(f"    ℹ {f['symbole']:<10} +{f['ecart']:.6f} ({f['part']:.2%}) — "
              "frais crypto prélevés en nature, hors historique des ordres")
    if verdict["conforme"]:
        print("    ✓ chaque lot ouvert reconstruit a sa contrepartie chez le courtier.")
    else:
        print(f"    ✗ {len(verdict['ecarts'])} écart(s) :")
        for e in verdict["ecarts"][:15]:
            print(f"        {e['symbole']:<10} journal {e['journal']:14.6f}  "
                  f"courtier {e['courtier']:14.6f}  écart {e['ecart']:+12.6f}")


def _appliquer(r, horo: str) -> None:
    from packages.storage import SqliteTradeJournal
    journal = SqliteTradeJournal()
    anciens = journal.all()
    src = ROOT / "data" / "journal.db"
    if src.exists():
        dest = src.with_suffix(f".avant-reconstruction-{horo}.db")
        shutil.copy2(src, dest)
        print(f"\n  Sauvegarde : {dest.name}")
    piste = ROOT / "data" / f"journal-avant-reconstruction-{horo}.json"
    piste.write_text(json.dumps(
        [{"id": t.id, "symbole": str(t.instrument), "qty": t.qty,
          "entree": str(t.entry_ts), "sortie": str(t.exit_ts) if t.exit_ts else None,
          "pnl_net": t.pnl_net} for t in anciens],
        indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(f"  Archive de l'ancien registre ({len(anciens)} lots) : {piste.name}")

    journal.supprimer([str(t.id) for t in anciens])
    n = 0
    for i, lot in enumerate(r.fermes):
        journal.append(_record(lot, i, ferme=True), legacy=True)
        n += 1
    for i, lot in enumerate(r.ouverts):
        journal.append(_record(lot, 10_000 + i, ferme=False), legacy=True)
        n += 1
    print(f"  {n} enregistrement(s) écrit(s) depuis les fills du courtier.")
    print("  Vérifier :  make diag-journal")


def main() -> int:
    print(__doc__.split("    python")[0].rstrip())
    from packages.research.reconstruction_journal import confronter, rejouer

    c = _courtier()
    if not c.get("lisible"):
        print(f"\n  ✗ COURTIER ILLISIBLE : {c.get('motif')}")
        print("    Sans l'historique réel, il n'y a rien à reconstruire — et")
        print("    reconstruire depuis l'ancien journal reproduirait ses défauts.")
        return 2
    if not c["fills"]:
        print("\n  ✗ AUCUN FILL rendu par le courtier — on ne vide pas un registre")
        print("    pour le remplacer par rien.")
        return 2

    r = rejouer(c["fills"])
    verdict = confronter(r, c["positions"])
    _rapport(r, c, verdict)

    if not verdict["conforme"]:
        print("\n  ✗ REFUS D'ÉCRIRE. Un registre reconstruit qui ne retombe pas sur")
        print("    l'inventaire réel est faux. Cause la plus fréquente : l'historique")
        print("    des ordres est tronqué (cf. ventes sans lot ci-dessus).")
        return 2

    if "--appliquer" not in sys.argv:
        print("\n  SIMULATION — rien n'a été écrit. Le rejeu est CONFORME à")
        print("  l'inventaire ; relancer avec `--appliquer` pour le remplacer.")
        return 0

    _appliquer(r, f"{datetime.now():%Y%m%d-%H%M%S}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
