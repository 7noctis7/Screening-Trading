#!/usr/bin/env python3
"""Comble les colonnes `name` VIDES des seeds d'univers, depuis les fournisseurs de données.

POURQUOI UN SCRIPT ET NON UNE SAISIE. `data/seed/us_extended.csv` liste des tickers sans
nom (BK, EA, NDX…). Les compléter à la main reviendrait à écrire dans le dépôt des libellés
issus d'une mémoire, sans source ni date — exactement ce que le mandat données-réelles
interdit. Un nom faux est pire qu'un nom absent : absent, il alerte ; faux, il rassure.

Le script n'écrit QUE ce qu'un fournisseur a répondu, ne touche jamais un nom déjà présent,
et rend compte de ce qu'il n'a pas pu résoudre.

    python scripts/completer_noms_univers.py --dry-run     # rapport seul
    python scripts/completer_noms_univers.py               # écrit les CSV
"""
from __future__ import annotations

import argparse
import csv
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))
SEEDS = RACINE / "data" / "seed"


def nom_fournisseur(symbole: str) -> tuple[str, str | None]:
    """(symbole, nom long) selon yfinance. None si le fournisseur ne sait pas."""
    try:
        import yfinance as yf
        info = yf.Ticker(symbole).get_info() or {}
        nom = info.get("longName") or info.get("shortName")
        return symbole, (str(nom).strip() or None) if nom else None
    except Exception:  # noqa: BLE001 — hors-ligne, symbole inconnu : l'absence se dit
        return symbole, None


def _manquants(chemin: Path) -> list[str]:
    with chemin.open(encoding="utf-8") as f:
        return [r["symbol"] for r in csv.DictReader(f)
                if r.get("symbol") and not (r.get("name") or "").strip()]


def _reecrire(chemin: Path, noms: dict[str, str]) -> int:
    with chemin.open(encoding="utf-8") as f:
        lecteur = csv.DictReader(f)
        colonnes, lignes = lecteur.fieldnames or [], list(lecteur)
    ecrits = 0
    for ligne in lignes:
        if not (ligne.get("name") or "").strip() and noms.get(ligne["symbol"]):
            ligne["name"], ecrits = noms[ligne["symbol"]], ecrits + 1
    if ecrits:
        with chemin.open("w", encoding="utf-8", newline="") as f:
            redacteur = csv.DictWriter(f, fieldnames=colonnes)
            redacteur.writeheader()
            redacteur.writerows(lignes)
    return ecrits


def principal() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="rapport sans écriture")
    args = ap.parse_args()

    fichiers = sorted(SEEDS.glob("*.csv"))
    trous = {c: _manquants(c) for c in fichiers}
    total = sum(len(v) for v in trous.values())
    if not total:
        print("Aucun nom manquant dans les seeds.")
        return 0
    print(f"→ {total} symbole(s) sans nom dans {sum(1 for v in trous.values() if v)} fichier(s).")

    tous = sorted({s for v in trous.values() for s in v})
    with ThreadPoolExecutor(max_workers=8) as pool:
        resolus = dict(pool.map(nom_fournisseur, tous))
    trouves = {s: n for s, n in resolus.items() if n}
    print(f"  {len(trouves)}/{len(tous)} résolus par le fournisseur.")

    introuvables = [s for s in tous if s not in trouves]
    if introuvables:
        print("  NON RÉSOLUS (laissés vides, jamais devinés) :")
        print("   ", ", ".join(introuvables[:40]) + (" …" if len(introuvables) > 40 else ""))

    if args.dry_run:
        for symbole in tous[:20]:
            print(f"    {symbole:12s} → {trouves.get(symbole) or '— introuvable —'}")
        return 0

    ecrits = sum(_reecrire(chemin, trouves) for chemin, manque in trous.items() if manque)
    print(f"→ {ecrits} nom(s) écrit(s). Relancer `make site` ou redémarrer l'API pour les voir.")
    return 0


if __name__ == "__main__":
    raise SystemExit(principal())
