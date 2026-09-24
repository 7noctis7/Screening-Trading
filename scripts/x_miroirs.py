#!/usr/bin/env python3
"""Quel miroir RSS de X répond AUJOURD'HUI ? Sonde, et rend la ligne à coller.

    make x-miroirs                                  # les comptes suivis
    make x-miroirs ARGS="--comptes astekz,elonmusk"
    make x-miroirs ARGS="--miroirs https://un.autre/{compte}/rss"

POURQUOI UN SONDEUR PLUTÔT QU'UNE LISTE. Le palier gratuit de l'API X ne permet pas de
LIRE. Les seules voies automatiques sans frais passent par un tiers qui republie X en
RSS — et ces instances MEURENT en permanence, parce qu'elles dépendent du bon vouloir
de X. Écrire « utilisez tel miroir » dans une documentation revient à la dater : la
réponse juste est celle qu'on MESURE le jour où l'on en a besoin.

Ce script ne sait donc rien ; il essaie et il rapporte. Les candidats ci-dessous sont
un point de départ à faire vieillir, pas une recommandation — et `--miroirs` permet
d'en essayer d'autres sans toucher au code.

CE QUI COMPTE N'EST PAS LE CODE HTTP MAIS LE NOMBRE D'ÉLÉMENTS. Une instance éteinte
répond souvent 200 avec une page d'excuse, et un flux vide ressemble à un compte muet.
On compte donc les `<item>` : c'est la seule preuve que quelque chose est lisible.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import sys
import urllib.error
import urllib.request
from pathlib import Path
from xml.etree import ElementTree

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

DELAI_S = 20.0
AGENT = "Mozilla/5.0 (compatible; QuantTerminal/1.0)"

# Candidats CONNUS AU 24/09/2026, à faire vieillir. `twiiit` est un redirecteur : il
# renvoie vers une instance vivante, ce qui le rend plus durable qu'une instance nommée.
CANDIDATS = (
    "https://twiiit.com/{compte}/rss",
    "https://xcancel.com/{compte}/rss",
    "https://nitter.poast.org/{compte}/rss",
    "https://nitter.privacydev.net/{compte}/rss",
    "https://nitter.net/{compte}/rss",
    "https://openrss.org/x.com/{compte}",
)
COMPTES = ("astekz", "trendspider", "micro2macr0", "eliz883")


def sonder(url: str) -> tuple[int, str]:
    """(nombre d'éléments, motif). 0 élément n'est JAMAIS une réussite silencieuse."""
    requete = urllib.request.Request(url, headers={"User-Agent": AGENT})
    try:
        with urllib.request.urlopen(requete, timeout=DELAI_S) as r:  # noqa: S310
            brut = r.read()
    except urllib.error.HTTPError as e:
        return 0, f"HTTP {e.code}"
    except (urllib.error.URLError, OSError) as e:
        return 0, f"{type(e).__name__}"
    try:
        racine = ElementTree.fromstring(brut)
    except ElementTree.ParseError:
        return 0, "réponse illisible (page d'excuse ?)"
    # LA RACINE TRANCHE, pas seulement le nombre d'éléments. Une page d'excuse minimale
    # est du XML PARFAITEMENT VALIDE : `<html><body>indisponible</body></html>` se parse
    # sans erreur et rend zéro `<item>`, donc « flux vide » — indiscernable d'un compte
    # qui n'a rien publié. Un test l'a montré ; la distinction est ici.
    if racine.tag.split("}")[-1].lower() not in ("rss", "feed", "rdf"):
        return 0, f"ce n'est pas un flux (racine <{racine.tag.split('}')[-1]}>)"
    items = racine.findall(".//item") or racine.findall(
        ".//{http://www.w3.org/2005/Atom}entry")
    return len(items), "ok" if items else "flux vide"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--comptes", default=",".join(COMPTES))
    ap.add_argument("--miroirs", default=",".join(CANDIDATS),
                    help="gabarits avec {compte}, séparés par des virgules")
    a = ap.parse_args()

    comptes = [c.strip() for c in a.comptes.split(",") if c.strip()]
    gabarits = [m.strip() for m in a.miroirs.split(",") if m.strip()]
    print(f"Sondage de {len(gabarits)} miroir(s) × {len(comptes)} compte(s)…\n")

    taches = {(g, c): g.format(compte=c) for g in gabarits for c in comptes}
    with cf.ThreadPoolExecutor(max_workers=8) as pool:
        resultats = dict(zip(taches, pool.map(sonder, taches.values()), strict=False))

    vivants: dict[str, list[str]] = {}
    for gabarit in gabarits:
        hote = gabarit.split("/")[2]
        lignes = []
        for compte in comptes:
            n, motif = resultats[(gabarit, compte)]
            marque = "✓" if n else "·"
            lignes.append(f"    {marque} {compte:16} {n:>3} élément(s)  {motif}")
            if n:
                vivants.setdefault(gabarit, []).append(compte)
        total = sum(resultats[(gabarit, c)][0] for c in comptes)
        etat = f"VIVANT ({total} éléments)" if total else "MORT"
        print(f"  {hote:28} {etat}")
        print("\n".join(lignes))
    return _conclure(vivants, comptes)


def _conclure(vivants: dict[str, list[str]], comptes: list[str]) -> int:
    print()
    if not vivants:
        print("AUCUN miroir ne répond. Ce n'est pas une panne de ce script : ces")
        print("instances meurent régulièrement. Deux recours, déjà en place :")
        print("  · Telegram, quand le compte y double ses messages ;")
        print("  · l'export navigateur — make x-export — qui ne dépend de personne.")
        return 1

    meilleur = max(vivants, key=lambda g: len(vivants[g]))
    couverts = vivants[meilleur]
    manquants = [c for c in comptes if c not in couverts]
    hote = meilleur.split("/")[2]
    print(f"MEILLEUR MIROIR : {hote} — {len(couverts)}/{len(comptes)} lisible(s).\n")
    print("À coller dans .env :")
    print("QUANT_X_RSS=" + ",".join(meilleur.format(compte=c) for c in couverts))
    print("\nPuis :  make x-ingest ARGS=\"--source rss\"")
    if manquants:
        print(f"\nNON COUVERTS par ce miroir : {', '.join(manquants)}.")
        print("Un compte absent du miroir n'est pas forcément inactif — essayez un")
        print("autre gabarit ci-dessus, ou l'export navigateur pour ceux-là.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
