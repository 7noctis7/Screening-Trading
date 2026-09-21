#!/usr/bin/env python3
"""Ce que les rebalancements EN DOUBLE ont coûté — sur l'historique RÉEL du courtier.

  python scripts/cout_churn.py                 # rapport complet
  python scripts/cout_churn.py --jours 30      # fenêtre récente
  python scripts/cout_churn.py --json          # pour un autre outil

POURQUOI CE SCRIPT EXISTE. Le 15/09, trois planificateurs visaient le même compte paper et
le doublon a coûté −60,79 $ en une journée. Restait la vraie question : depuis QUAND ? Le
runner cloud et le VPS coexistaient depuis des semaines ; seul le Mac était intermittent.
Tant que ce n'est pas chiffré, la courbe d'equity paper — et tout ce qu'on en déduit —
compare une stratégie à elle-même plus du bruit d'exécution que personne n'a décidé.

IL NE DEVINE RIEN. Il lit l'historique d'ordres du courtier et applique l'invariant de
`packages.execution.passages` : une réconciliation envoie au plus un ordre par symbole,
donc deux ordres de sens opposé sur un symbole le même jour sont deux passages qui se
contredisent. Sans courtier joignable, il le DIT et sort — il n'invente pas de série.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

def _ordres() -> tuple[list[dict], str]:
    """Délègue au paquet : `daily_brief` a besoin de la MÊME lecture, et ne peut pas
    importer un script (`scripts/` n'est pas un paquet)."""
    from packages.execution.historique_courtier import ordres_reels
    return ordres_reels()


def _filtrer(ordres: list[dict], jours: int | None) -> list[dict]:
    if not jours:
        return ordres
    from packages.execution.passages import jour_utc
    borne = (datetime.now(UTC) - timedelta(days=jours)).date()
    return [o for o in ordres
            if (j := jour_utc(str(o.get("date") or ""))) and j >= borne]


def _ligne_jour(j: dict) -> str:
    ar = j["allers_retours"]
    marque = "  " if j["n_passages"] <= 1 else "⚠ "
    heures = " ".join(j["heures"][:4]) + ("…" if len(j["heures"]) > 4 else "")
    cout = f"{ar['pnl']:+9.2f} $" if ar["n_lignes"] else "         —"
    return (f"{marque}{j['jour']}  {j['n_passages']} passage(s) [{heures:<26s}] "
            f"{j['n_ordres']:3d} ordres · {ar['n_lignes']:2d} A/R · {cout}")


def afficher(rap: dict) -> None:
    print(f"\n{'':2s}{'JOUR':10s}  passages  heures UTC"
          f"{'':20s}ordres · allers-retours · coût")
    print("  " + "─" * 88)
    for j in rap["jours"]:
        print(_ligne_jour(j))
    n2 = len(rap["jours_a_doublon"])
    print("  " + "─" * 88)
    print(f"  {rap['n_jours']} jour(s) d'activité · {n2} avec PLUS D'UN passage")
    if rap["depuis"]:
        print(f"  ⚠ Premier doublon : {rap['depuis']} — deux passages le même jour.")
    if rap["depuis_cout"]:
        # La date qui compte n'est pas celle du premier doublon mais celle du premier
        # doublon qui se CONTREDIT : deux passages aboutissant à la même cible ne coûtent
        # rien. Dater la pollution du premier doublon condamnerait des semaines correctes.
        print(f"  ⚠ Premier ALLER-RETOUR : {rap['depuis_cout']} — c'est DEPUIS CETTE DATE "
              "que la courbe d'equity porte du churn.")
        from packages.execution.annotation_churn import _montant
        signe = "-" if rap["pnl_churn"] < 0 else "+"
        print(f"  ⚠ Coût cumulé : {signe}{_montant(rap['pnl_churn'])} $ sur "
              f"{_montant(rap['notionnel_churn'], 0)} $ brassés "
              f"({len(rap['jours_a_cout'])} jour(s) concerné(s)).")
    elif rap["depuis"]:
        print("  ✓ Des doublons, mais AUCUN aller-retour : les passages ont abouti à la "
              "même cible. Rien à déduire de la courbe.")
    else:
        print("  ✓ Aucun jour à doublon sur la fenêtre : un seul passage par journée.")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--jours", type=int, default=None, help="limiter aux N derniers jours")
    ap.add_argument("--json", action="store_true", help="sortie machine")
    a = ap.parse_args()

    ordres, motif = _ordres()
    if motif:
        print(f"⛔ Historique indisponible : {motif}", file=sys.stderr)
        print("   Ce rapport ne s'écrit QUE sur des ordres réels — aucune estimation.",
              file=sys.stderr)
        return 2

    from datetime import UTC, datetime

    from packages.execution.annotation_churn import annotation, ecrire_cache
    from packages.execution.passages import rapport
    rap = rapport(_filtrer(ordres, a.jours))

    # LE RAPPORT EST POSÉ SUR DISQUE, parce que c'est ici — et seulement ici — qu'on a
    # l'historique du courtier. Le site le relit sans réseau pour ANNOTER sa courbe
    # d'equity réelle ; sans ce dépôt, la page ne pourrait que se taire, et un silence
    # se lit comme « rien à signaler ».
    quand = datetime.now(UTC).isoformat(timespec="seconds")
    if a.jours is None:            # un rapport TRONQUÉ ne doit pas écraser l'entier
        try:
            ecrire_cache(rap, quand)
        except Exception as e:  # noqa: BLE001 — un cache non écrit n'invalide pas la mesure
            print(f"⚠ cache non écrit ({type(e).__name__}: {e})", file=sys.stderr)

    if a.json:
        print(json.dumps(rap, ensure_ascii=False, indent=2))
        return 0
    afficher(rap)
    note = annotation(rap, mesure_le=quand)
    if note["applicable"]:
        print(f"\n  ANNOTATION DE LA COURBE RÉELLE\n  {note['texte']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
