"""Route de l'onglet X : lire le flux, le filtrer, et DIRE quand il n'y a rien.

Le danger d'une page de filtres n'est pas le filtre, c'est le VIDE. « Aucun résultat »
peut vouloir dire trois choses incompatibles — le flux n'est pas branché, il est branché
mais vide, ou vos critères ne laissent rien passer — et un écran qui ne les distingue
pas laisse l'utilisateur conclure au hasard. La charge rend donc `disponible`,
`total_stock` et `filtres_actifs` séparément, pour que l'écran puisse le dire.

Le filtrage n'est pas réimplémenté ici : il délègue à `packages.social.filtres`, qui
porte la sémantique (sélection vide = tous, recherche insensible à la casse et aux
accents, plusieurs mots en ET).
"""

from __future__ import annotations

from typing import Any

from packages.social.filtres import Filtre, appliquer
from packages.social.modele import Classification, Direction, Publication
from packages.social.qualification import verdict
from packages.social.store import StorePublications, chemin_db

LIMITE_DEFAUT = 200


def _liste(brut: str) -> list[str]:
    """« a,b » ou « a » donne ['a','b']. Une chaîne vide ne filtre RIEN."""
    return [x.strip() for x in brut.split(",") if x.strip()]


def _enums(brut: str, cls: type) -> list[Any]:
    """Une valeur inconnue est IGNORÉE, jamais fatale : l'URL vient du dehors."""
    valides = {e.value.lower(): e for e in cls}
    return [valides[v.lower()] for v in _liste(brut) if v.lower() in valides]


def construire_filtre(accounts: str = "", q: str = "", classification: str = "",
                      direction: str = "", symbol: str = "",
                      ticker: str = "") -> Filtre:
    return Filtre(
        comptes=_liste(accounts), requete=q,
        classifications=_enums(classification, Classification),
        directions=_enums(direction, Direction),
        symboles=_liste(symbol), tickers=_liste(ticker))


def _serialiser(p: Publication) -> dict:
    """Chaque publication part AVEC son verdict. Jamais l'une sans l'autre.

    AGENTS.md §9 impose un point d'entrée unique, `intelligence.pipeline.qualifier()`.
    Sérialiser sans lui rouvrirait la seconde voie que cette règle ferme : des propos
    affichés sans plafond d'authenticité ni exigence de corroboration. Le verdict est
    donc calculé ICI, dans la fonction par laquelle tout sort, et non dans l'appelant —
    un appelant s'oublie.
    """
    return {"id": p.id, "compte": p.compte, "ts": p.ts.isoformat(), "texte": p.texte,
            "classification": str(p.classification), "ticker": p.ticker,
            "symbole": p.symbole,
            "direction": None if p.direction is None else str(p.direction),
            "extraits": p.extraits, "url": p.url, "verdict": verdict(p)}


def publications(f: Filtre, limite: int = LIMITE_DEFAUT, db: str | None = None) -> dict:
    """Charge, filtre, et rend de quoi distinguer les trois formes de vide."""
    try:
        store = StorePublications(db or chemin_db())
    except Exception as e:  # noqa: BLE001 — une base illisible n'est pas un flux vide
        return _indisponible(f"base illisible : {e}")
    try:
        toutes = store.toutes()
        comptes, symboles = store.comptes(), store.symboles()
    finally:
        store.close()

    if not toutes:
        return _indisponible("flux non connecté : aucune publication ingérée")

    gardees = appliquer(toutes, f)
    return {
        "disponible": True, "raison": None,
        "total_stock": len(toutes), "n": len(gardees),
        "filtres_actifs": f.actif(),
        "tronque": len(gardees) > limite,
        "comptes": comptes, "symboles": symboles,
        "classifications": [str(c) for c in Classification],
        "directions": [str(d) for d in Direction],
        "publications": [_serialiser(p) for p in gardees[:limite]],
    }


def _indisponible(raison: str) -> dict:
    """ABSENT N'EST PAS ZÉRO : `total_stock` vaut None, pas 0 — on ne sait pas."""
    return {"disponible": False, "raison": raison, "total_stock": None, "n": 0,
            "filtres_actifs": False, "tronque": False,
            "comptes": [], "symboles": [],
            "classifications": [str(c) for c in Classification],
            "directions": [str(d) for d in Direction], "publications": []}
