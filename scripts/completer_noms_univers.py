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
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))
SEEDS = RACINE / "data" / "seed"


# TROIS causes d'échec, et les confondre rend le rapport inexploitable. Constaté le 07/09
# sur un premier jet de ce script : `ATVI`, `CELG`, `FRC` sont délistés ; `BK`, `HES`,
# `HOLX` sont bien vivants mais le fournisseur n'avait pas répondu (débit limité) ;
# `AAVE/USDC` échoue parce que yfinance ne connaît pas ce format de paire. Les afficher
# tous en « introuvable » laisserait conclure que l'univers est plein de titres morts.
INCONNU = "inconnu du fournisseur"      # le fournisseur a répondu : il ne connaît pas
MUET = "aucune réponse"                  # débit limité, réseau : on ne sait PAS


def _essayer(symbole: str) -> tuple[str | None, str | None]:
    """(nom, cause d'échec). Distingue « il ne connaît pas » de « il n'a pas répondu »."""
    import yfinance as yf
    try:
        info = yf.Ticker(symbole).get_info() or {}
    except Exception as erreur:  # noqa: BLE001
        texte = str(erreur).lower()
        muet = any(m in texte for m in ("rate", "limit", "timeout", "connection", "429"))
        return None, (MUET if muet else INCONNU)
    nom = info.get("longName") or info.get("shortName")
    return (str(nom).strip() or None, None) if nom else (None, INCONNU)


def nom_fournisseur(couple: tuple[str, str | None], essais: int = 3) -> tuple[str, str | None, str | None]:
    """(symbole, nom, cause). Essaie aussi les ALIAS — `AAVE/USDC` se demande `AAVE-USD`.

    LA CLASSE D'ACTIF EST OBLIGATOIRE, et ce n'est pas du zèle. Sans elle, le 07/09, `ABC`
    (AmerisourceBergen, action délistée) recevait le nom « Abell Coin USD » : le repli
    `-USD`, conçu pour retrouver `ETH-USD` depuis `ETH`, avait trouvé une cryptomonnaie.
    Le script s'apprêtait à écrire ce nom dans le dépôt. Un nom faux ne se signale pas
    comme faux — il se lit, il rassure, et il traverse toutes les vérifications suivantes.

    Les alias viennent de `user_analysis._aliases`, la MÊME fonction qui résout les prix :
    un symbole valorisé sous un alias doit être nommé sous le même, sinon la colonne
    « nom » décrirait un autre instrument que la colonne « prix ».
    """
    from packages.portfolio.user_analysis import _aliases
    symbole, classe = couple
    cause = None
    for candidat in _aliases(symbole, classe):
        for tentative in range(essais):
            nom, echec = _essayer(candidat)
            if nom:
                return symbole, nom, None
            cause = echec
            if echec != MUET:
                break                                   # inutile d'insister : il ne connaît pas
            time.sleep(1.5 * (tentative + 1))            # débit limité : on laisse respirer
    return symbole, None, cause


def _manquants(chemin: Path) -> list[tuple[str, str | None]]:
    """(symbole, classe d'actif) des lignes sans nom. La classe borne les alias essayés."""
    with chemin.open(encoding="utf-8") as f:
        return [(r["symbol"], (r.get("asset_class") or "").strip() or None)
                for r in csv.DictReader(f)
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
    ap.add_argument("--fils", type=int, default=3, help="requêtes en parallèle (défaut 3)")
    args = ap.parse_args()

    fichiers = sorted(SEEDS.glob("*.csv"))
    trous = {c: _manquants(c) for c in fichiers}
    total = sum(len(v) for v in trous.values())
    if not total:
        print("Aucun nom manquant dans les seeds.")
        return 0
    print(f"→ {total} symbole(s) sans nom dans {sum(1 for v in trous.values() if v)} fichier(s).")

    tous = sorted({couple for v in trous.values() for couple in v})
    # Parallélisme MODÉRÉ : à 8 fils, le fournisseur limite le débit et rend des silences
    # qu'on prendrait pour des titres délistés. Mieux vaut plus lent et interprétable.
    with ThreadPoolExecutor(max_workers=args.fils) as pool:
        resultats = list(pool.map(nom_fournisseur, tous))
    trouves = {s: n for s, n, _ in resultats if n}
    par_cause: dict[str, list[str]] = {}
    for symbole, nom, cause in resultats:
        if not nom:
            par_cause.setdefault(cause or INCONNU, []).append(symbole)
    print(f"  {len(trouves)}/{len(tous)} résolus par le fournisseur.")
    for cause, symboles in sorted(par_cause.items()):
        etiquette = ("PROBABLEMENT DÉLISTÉS ou renommés — à retirer de l'univers"
                     if cause == INCONNU else
                     "NON MESURÉS (débit limité) — relancer, ce ne sont PAS des titres morts")
        print(f"  {len(symboles)} × {cause} → {etiquette}")
        print("   ", ", ".join(symboles[:30]) + (" …" if len(symboles) > 30 else ""))

    if args.dry_run:
        print("\n  Aperçu :")
        for symbole, nom, cause in resultats[:20]:
            print(f"    {symbole:12s} → {nom or f'— {cause} —'}")
        return 0

    ecrits = sum(_reecrire(chemin, trouves) for chemin, manque in trous.items() if manque)
    print(f"→ {ecrits} nom(s) écrit(s). Relancer `make site` ou redémarrer l'API pour les voir.")
    return 0


if __name__ == "__main__":
    raise SystemExit(principal())
