#!/usr/bin/env python3
"""Reconstitue au journal les ACHATS que le compte a exécutés et que le registre ignore.

L'ORDRE DES DEUX RÉPARATIONS COMPTE. `reconcilier_journal` ferme des lots avec les
ventes réelles ; il ne peut fermer que ce qui existe. Un achat jamais journalisé n'a pas
de lot, donc pas de sortie possible, et la vente correspondante reste sans contrepartie.
On complète donc les ENTRÉES d'abord, les SORTIES ensuite :

    python scripts/completer_ouvertures.py                 # SIMULATION (par défaut)
    python scripts/completer_ouvertures.py --appliquer      # écrit, après sauvegarde
    python scripts/reconcilier_journal.py --appliquer       # puis les fermetures
    make diag-journal                                       # et on vérifie

CE QUE L'OUTIL ÉCRIT — et sous quel régime. Un lot par symbole incomplet, `legacy=1`,
portant la quantité manquante, le VWAP des fills NON couverts et la date du premier
d'entre eux. `legacy=1` n'est pas un rangement commode : ces fills sont importés après
coup, leurs features de décision n'ont jamais été capturées et ne peuvent plus l'être —
c'est la définition du drapeau. Les mettre en `legacy=0` gonflerait de trades aveugles
la statistique même qu'on cherche à rendre fiable.

CE QU'IL N'ÉCRIT PAS. Rien pour un courtier muet (un silence n'est pas une mesure), rien
là où le journal en sait PLUS que le courtier — cet écart-là est signalé, jamais
« corrigé » en retirant des lots.
"""

from __future__ import annotations

import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

LIMITE_ORDRES = 5000


def _ordres_courtiers(limite: int = LIMITE_ORDRES) -> list[dict]:
    """Ordres exécutés des DEUX courtiers. Un courtier injoignable est dit, pas suppléé.

    Le diagnostic ne lisait qu'Alpaca — d'où une poche crypto qui semblait absente de
    partout alors qu'elle n'était simplement jamais demandée."""
    ordres: list[dict] = []
    for nom, fabrique in (("Alpaca", _alpaca), ("Bitmart", _bitmart)):
        try:
            lot = fabrique(limite)
        except Exception as e:  # noqa: BLE001
            print(f"  {nom} injoignable ({str(e)[:60]}) — ses symboles resteront "
                  "incomplets, aucun lot ne sera inventé pour eux.")
            continue
        print(f"  {nom} : {len(lot)} ordre(s) exécuté(s).")
        ordres += lot
    return ordres


def _alpaca(limite: int) -> list[dict]:
    from packages.execution.alpaca_broker import AlpacaBroker
    return [{**o, "broker": o.get("broker") or "Alpaca"}
            for o in AlpacaBroker().orders(limit=limite)]


def _bitmart(limite: int) -> list[dict]:
    from packages.execution.bitmart_broker import BitmartBroker
    return BitmartBroker(dry_run=False).orders(limit=limite)


def _horodatage(brut) -> datetime | None:
    """Date de fill en UTC AWARE, ou None. Une date nue produirait un datetime naïf,
    et la comparer à une entrée aware lève une TypeError EN PLEINE ÉCRITURE."""
    try:
        ts = datetime.fromisoformat(str(brut).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return ts if ts.tzinfo else ts.replace(tzinfo=UTC)


def _record(lot: dict):
    """TradeRecord d'ouverture correctrice, ou None si la date du fill est illisible.

    `id` déterministe par symbole : un second passage UPSERTe le même enregistrement au
    lieu d'en empiler un nouveau. Combiné au recalcul de l'écart (qui tombe à zéro une
    fois le lot écrit), l'outil est rejouable sans jamais doubler quoi que ce soit."""
    from packages.core.models import AssetClass, Side, TradeRecord
    from packages.research.completion_ouvertures import MOTIF
    ts = _horodatage(lot["date"])
    if ts is None:
        return None
    crypto = (lot.get("venue") or "").lower() == "bitmart"
    return TradeRecord(
        id=f"C-{lot['symbole']}", instrument=lot["symbole"],
        asset_class=AssetClass.CRYPTO if crypto else AssetClass.EQUITY,
        venue=lot.get("venue") or "Alpaca", side=Side.LONG, qty=float(lot["qty"]),
        entry_ts=ts, entry_price=float(lot["prix"]), avg_price=float(lot["prix"]),
        entry_reason=f"{MOTIF}: VWAP des fills non couverts", features_snapshot={})


def _resume(a_creer: list[dict], en_trop: list[dict]) -> None:
    print(f"\n  PLAN — {len(a_creer)} ouverture(s) à reconstituer, "
          f"{len(en_trop)} symbole(s) où le journal en sait PLUS que le courtier\n")
    for x in sorted(a_creer, key=lambda d: -d["qty"] * d["prix"])[:15]:
        print(f"    {x['symbole']:<12} {x['qty']:>12.4f} @ {x['prix']:>10.4f} "
              f"le {x['date'][:10]}   (acheté {x['achete']:.4f}, "
              f"journal {x['journal']:.4f})")
    if len(a_creer) > 15:
        print(f"    … et {len(a_creer) - 15} autres")
    if a_creer:
        expo = sum(x["qty"] * x["prix"] for x in a_creer)
        print(f"\n    Coût de revient reconstitué : {expo:,.2f} $".replace(",", " "))
    for x in en_trop[:10]:
        print(f"    ⚠️ {x['symbole']:<12} journal {x['journal']:.4f} > "
              f"courtier {x['achete']:.4f} — SIGNALÉ, non corrigé.")
    if en_trop:
        print("       Historique du courtier tronqué, ou lots fantômes : à trancher")
        print("       avec `make diag-journal`, pas en supprimant des lots ici.")


def main() -> None:
    print(__doc__.split("    python")[0].rstrip())
    from packages.research.completion_ouvertures import (
        ouvertures_manquantes,
        quantites_journalisees,
    )
    from packages.storage import SqliteTradeJournal
    journal = SqliteTradeJournal()
    ordres = _ordres_courtiers()
    if not ordres:
        print("\n  Aucun ordre récupéré — rien ne peut être reconstitué sans la vérité "
              "du courtier.")
        return
    a_creer, en_trop = ouvertures_manquantes(
        ordres, quantites_journalisees(journal.all()))
    _resume(a_creer, en_trop)
    if not a_creer:
        print("\n  Le journal couvre tous les achats du courtier — rien à écrire.")
        return
    if "--appliquer" not in sys.argv:
        print("\n  SIMULATION — rien n'a été écrit. Relancer avec `--appliquer`.")
        return
    src = ROOT / "data" / "journal.db"
    if src.exists():
        dest = src.with_suffix(f".avant-completion-{datetime.now():%Y%m%d-%H%M%S}.db")
        shutil.copy2(src, dest)
        print(f"\n  Sauvegarde : {dest.name}")
    n = 0
    for lot in a_creer:
        rec = _record(lot)
        if rec is None:
            continue                                  # date illisible → on n'écrit pas
        journal.append(rec, legacy=True)
        n += 1
    print(f"  {n} ouverture(s) reconstituée(s) "
          "(legacy=1, hors statistiques affichées).")
    print("  Enchaîner : python scripts/reconcilier_journal.py --appliquer, "
          "puis make diag-journal.")


if __name__ == "__main__":
    main()
