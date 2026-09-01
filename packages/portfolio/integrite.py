"""Intégrité des séries : un NaN est un INCIDENT DE DONNÉES, jamais une valeur.

Constaté le 31/08. La CI est passée du vert au rouge sur un code identique : deux tests
ont échoué sur `assert nan <= nan` et `assert nan > 0`. Cause : un téléchargement réseau
incomplet a laissé un point non fini dans une courbe d'equity, et ce point s'est propagé
EN SILENCE jusqu'aux métriques publiées.

LE MODE DE PANNE, ET POURQUOI IL EST GRAVE. Aujourd'hui il casse un test, donc on le
voit. Demain il peut produire un Sharpe ou une bande de projection à `nan` que le front
affiche comme « — » sans que personne ne sache qu'une donnée manquait. Une métrique
absente est un problème visible ; une métrique fausse ne l'est pas.

L'AMPLIFICATION PAR LE RÉÉCHANTILLONNAGE. `stress.mc_projection` tire les rendements
futurs AVEC REMISE dans le vivier observé. Un seul NaN parmi 2760 rendements apparaît
alors dans la quasi-totalité des 1000 trajectoires, et `cumprod` le propage jusqu'au
bout : les cinq percentiles sortent tous à `nan`. Un point sur 2760 suffit.

LA RÈGLE. On ne remplace jamais un NaN par une valeur inventée (0, la moyenne, le
dernier cours). On le COMPTE, on le DIT, et on calcule sur ce qui existe réellement.
"""

from __future__ import annotations

import math

PART_MIN_EXPLOITABLE = 0.90        # sous 90 % de points valides, on ne conclut pas


def _fini(v) -> bool:
    try:
        return math.isfinite(float(v))
    except (TypeError, ValueError):
        return False


def diagnostiquer(serie) -> dict:
    """Combien de points non finis, où commence le premier, quelle part reste."""
    vals = list(serie or [])
    n = len(vals)
    mauvais = [i for i, v in enumerate(vals) if not _fini(v)]
    return {
        "n": n,
        "n_non_finis": len(mauvais),
        "premier_non_fini": mauvais[0] if mauvais else None,
        "part_valide": round((n - len(mauvais)) / n, 4) if n else 0.0,
        "saine": not mauvais,
    }


def prefixe_fini(courbe) -> tuple[list[float], dict]:
    """Préfixe d'une COURBE D'EQUITY jusqu'au premier point non fini.

    On tronque au lieu de filtrer : après un trou, la capitalisation est rompue, et
    recoller les deux morceaux fabriquerait un rendement qui n'a jamais existé — celui
    qui enjambe le trou. Tronquer perd de l'information ; recoller en invente.
    """
    diag = diagnostiquer(courbe)
    vals = list(courbe or [])
    coupe = diag["premier_non_fini"]
    garde = vals if coupe is None else vals[:coupe]
    diag["n_conserves"] = len(garde)
    diag["tronquee"] = coupe is not None
    return [float(v) for v in garde], diag


def filtrer_finis(rendements) -> tuple[list[float], dict]:
    """Vivier de RENDEMENTS débarrassé des points non finis.

    Ici on filtre au lieu de tronquer, et la différence est de fond : un rendement
    inobservable n'appartient simplement pas à l'échantillon dans lequel on tire. Une
    courbe d'equity est une séquence — un vivier de rendements est un ensemble.
    """
    diag = diagnostiquer(rendements)
    garde = [float(v) for v in (rendements or []) if _fini(v)]
    diag["n_conserves"] = len(garde)
    return garde, diag


def exploitable(diag: dict, part_min: float = PART_MIN_EXPLOITABLE,
                min_points: int = 30) -> bool:
    """Reste-t-il assez de données VALIDES pour publier un chiffre ?

    Deux conditions, car chacune rate un cas de l'autre : une part élevée sur dix points
    ne vaut rien, et mille points valides sur dix mille décrivent une série trouée.
    """
    return (diag.get("n_conserves", 0) >= min_points
            and diag.get("part_valide", 0.0) >= part_min)


def verdict(diag: dict, part_min: float = PART_MIN_EXPLOITABLE) -> dict:
    """Diagnostic PUBLIABLE — pour que le front sache qu'une donnée manquait."""
    ok = exploitable(diag, part_min)
    return {
        **diag, "exploitable": ok,
        "motif": ("" if ok else
                  f"{diag.get('n_non_finis', 0)} point(s) non fini(s) sur "
                  f"{diag.get('n', 0)} — série trop trouée pour publier un chiffre"),
    }
