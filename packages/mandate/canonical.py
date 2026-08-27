"""Forme CANONIQUE d'un mandat — la seule chose qui rend un hash comparable.

Un hash de configuration ne vaut que si deux écritures du MÊME mandat produisent
le même octet. Sinon l'identité dérive au premier round-trip YAML et l'audit ne
prouve plus rien. Les pièges sont connus et tous silencieux :

    ordre des clés      {"a":1,"b":2} vs {"b":2,"a":1}   → même mandat
    flottant entier     30 vs 30.0                        → même mandat
    zéro signé          0.0 vs -0.0                       → même mandat
    espaces             json.dumps par défaut en ajoute   → même mandat
    non-fini            NaN, Infinity                     → REFUS, pas un mandat

Le choix de fond : `0.1` et `0.30000000000000004` hashent DIFFÉREMMENT, et c'est
voulu. Ce sont des nombres différents. Arrondir en douce ferait collisionner deux
configurations réellement distinctes — plus grave que le désagrément inverse. Un
paramètre de mandat se DÉCLARE, il ne se calcule pas : si tu écris `0.1 + 0.2`
dans un mandat, c'est le mandat qui est fautif, pas le hash.

Inspiré de RFC 8785 (JSON Canonicalization Scheme) sans en revendiquer la
conformité intégrale : on en reprend le tri des clés, la sérialisation compacte
et la normalisation des nombres entiers, qui sont les trois règles qui mordent ici.
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any

# Longueur du hash affiché. 16 hex = 64 bits : au-delà de 10^9 mandats la
# probabilité de collision reste < 10^-2 (anniversaire). Le hash COMPLET reste
# disponible ; c'est l'abrégé qui va dans les logs et les noms de fichiers.
LONGUEUR_COURTE = 16


def _nombre(x: float | int) -> Any:
    """Normalise un nombre. Un flottant entier devient un entier ; -0.0 devient 0."""
    if isinstance(x, bool):            # bool est un int en Python — à traiter AVANT
        return x
    if isinstance(x, int):
        return x
    v = float(x)
    if not math.isfinite(v):
        raise ValueError(
            f"valeur non finie dans un mandat : {v!r}. NaN et Infinity n'ont pas "
            "de représentation JSON et ne peuvent pas décrire une décision.")
    if v == 0.0:                       # écrase -0.0, qui hashe sinon à part
        return 0
    return int(v) if v.is_integer() else v


def normaliser(obj: Any) -> Any:
    """Applique `_nombre` récursivement et refuse ce qui n'est pas sérialisable.

    Les clés de dictionnaire sont contraintes à des chaînes : `json` convertirait
    silencieusement `1` en `"1"`, donc `{1: x}` et `{"1": x}` hasheraient pareil
    sans qu'on l'ait décidé.
    """
    if isinstance(obj, dict):
        for k in obj:
            if not isinstance(k, str):
                raise TypeError(
                    f"clé de mandat non textuelle : {k!r} ({type(k).__name__})")
        return {k: normaliser(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [normaliser(v) for v in obj]
    if isinstance(obj, (int, float)):
        return _nombre(obj)
    if obj is None or isinstance(obj, str):
        return obj
    raise TypeError(
        f"type non canonisable dans un mandat : {type(obj).__name__}. Un mandat "
        "est une DONNÉE — pas d'objet, pas de fonction, pas de date native.")


def canoniser(obj: Any) -> bytes:
    """Octets canoniques d'un mandat. Deux mandats égaux → octets identiques."""
    return json.dumps(
        normaliser(obj),
        sort_keys=True,                       # l'ordre d'écriture ne doit rien changer
        separators=(",", ":"),                # aucune espace insignifiante
        ensure_ascii=False,                   # UTF-8 réel, pas des \uXXXX
        allow_nan=False,                      # ceinture + bretelles avec `_nombre`
    ).encode("utf-8")


def hacher(obj: Any) -> str:
    """SHA-256 de la forme canonique, en hexadécimal complet."""
    return hashlib.sha256(canoniser(obj)).hexdigest()


def hacher_court(obj: Any) -> str:
    """Abrégé lisible du hash — pour les logs, les noms de fichiers, les tableaux."""
    return hacher(obj)[:LONGUEUR_COURTE]
