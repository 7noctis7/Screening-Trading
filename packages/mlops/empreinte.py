"""Empreintes SHA-256 — de quoi prouver qu'un artefact est bien celui qu'on croit.

POURQUOI PAS SEULEMENT `safe_pickle`. Celui-ci écrit déjà un sidecar `.sha256` à côté de
ce qu'il sérialise, et le vérifie au chargement : c'est la provenance d'un FICHIER. Il ne
sait rien dire d'un JEU DE DONNÉES en mémoire, qui n'est pas un fichier et dont on veut
pourtant figer l'identité dans un manifeste.

CE QU'UNE EMPREINTE DE DATASET DOIT GARANTIR. Deux entraînements sur les mêmes données
doivent donner la même empreinte, sur n'importe quelle machine, dans n'importe quel ordre
de parcours d'un dictionnaire. D'où : tri des clés, flottants normalisés, encodage fixé.
Sans cela l'empreinte varierait d'un poste à l'autre et ne prouverait plus rien — elle
donnerait même l'illusion inverse, celle d'un dataset qui change alors qu'il est identique.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

TAILLE_BLOC = 1 << 20          # 1 Mo : un modèle de plusieurs centaines de Mo ne tient pas en RAM
LONGUEUR_COURTE = 16           # préfixe lisible dans un nom de fichier ou un tableau


def sha256_fichier(chemin: str | Path) -> str:
    """Empreinte d'un fichier, lu par blocs."""
    h = hashlib.sha256()
    with Path(chemin).open("rb") as f:
        while bloc := f.read(TAILLE_BLOC):
            h.update(bloc)
    return h.hexdigest()


def _normaliser(o):
    """Rend une structure DÉTERMINISTE avant hachage.

    Les flottants sont la difficulté : `0.1 + 0.2` ne s'écrit pas pareil partout, et
    `NaN != NaN` empêche toute comparaison. On fixe donc une représentation — 12 décimales
    significatives, NaN et infinis nommés — plutôt que de laisser `repr()` décider.
    """
    if isinstance(o, float):
        if math.isnan(o):
            return "__nan__"
        if math.isinf(o):
            return "__inf__" if o > 0 else "__-inf__"
        return f"{o:.12g}"
    if isinstance(o, dict):
        return {str(k): _normaliser(o[k]) for k in sorted(o, key=str)}
    if isinstance(o, (list, tuple)):
        return [_normaliser(v) for v in o]
    if isinstance(o, (set, frozenset)):
        return sorted(_normaliser(v) for v in o)
    try:
        import numpy as _np
        if isinstance(o, _np.ndarray):
            return _normaliser(o.tolist())
        if isinstance(o, _np.generic):
            return _normaliser(o.item())
    except Exception:  # noqa: BLE001 — numpy optionnel
        pass
    return o


def empreinte(objet) -> str:
    """Empreinte stable d'une structure Python quelconque."""
    charge = json.dumps(_normaliser(objet), sort_keys=True, ensure_ascii=False,
                        separators=(",", ":"), default=str)
    return hashlib.sha256(charge.encode("utf-8")).hexdigest()


def empreinte_jeu(donnees: dict[str, object], *, colonnes: list[str] | None = None) -> str:
    """Empreinte d'un JEU DE DONNÉES d'entraînement, symbole par symbole.

    `colonnes` fige la liste et l'ORDRE des colonnes retenues : un dataset dont on change
    les features n'est pas le même dataset, même si les prix sont identiques. L'oublier
    ferait passer un changement de features pour une simple réexécution.
    """
    resume: dict[str, object] = {"__colonnes__": list(colonnes or [])}
    for sym in sorted(donnees, key=str):
        resume[str(sym)] = _resumer(donnees[sym])
    return empreinte(resume)


def _resumer(bloc) -> object:
    """Résumé hachable d'un bloc de données — forme, bornes, et contenu si petit."""
    try:
        import pandas as _pd
        if isinstance(bloc, _pd.DataFrame):
            return {"forme": list(bloc.shape), "colonnes": [str(c) for c in bloc.columns],
                    "debut": str(bloc.index[0]) if len(bloc) else "",
                    "fin": str(bloc.index[-1]) if len(bloc) else "",
                    # La somme par colonne détecte une valeur modifiée sans hacher des
                    # millions de lignes. Un dataset tronqué change déjà de forme.
                    "sommes": [f"{float(bloc[c].sum(skipna=True)):.6g}"
                               if _pd.api.types.is_numeric_dtype(bloc[c]) else "na"
                               for c in bloc.columns]}
    except Exception:  # noqa: BLE001 — pandas optionnel
        pass
    return _normaliser(bloc)


def verifier(chemin: str | Path, attendu: str) -> bool:
    """Le fichier porte-t-il l'empreinte annoncée ? Absent ou différent ⇒ False."""
    p = Path(chemin)
    if not p.exists() or not attendu:
        return False
    return sha256_fichier(p) == attendu


def court(h: str) -> str:
    """Préfixe lisible, pour un nom de version ou une colonne de tableau."""
    return (h or "")[:LONGUEUR_COURTE]
