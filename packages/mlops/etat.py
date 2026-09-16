"""L'état du REGISTRE de modèles — ce que `/api/ai/modeles` montre.

Ce module vivait dans `packages/nlp/sante.py`, à côté de l'état de la chaîne NLP locale.
Il n'avait rien à y faire : le registre décrit le modèle ML de production (entraînement,
jeu de données, commit), pas un fournisseur de LLM. Le voisinage les faisait tomber
ensemble — retirer la chaîne NLP aurait emporté la version du modèle affichée sur le site.

Une version écrite en dur dans le front se détache de ce qu'elle désigne (ADR-0154) : tout
ce qui est rendu ici vient du registre, y compris le fait qu'un modèle ait été entraîné
depuis un arbre git modifié — donc qu'il ne soit PAS reproductible depuis ce commit.
"""

from __future__ import annotations


def etat_modeles() -> dict:
    """Version en production et dernier entraînement, LUS DANS LE REGISTRE."""
    try:
        from packages.mlops.registre import Registre
        reg = Registre()
    except Exception as e:  # noqa: BLE001 — l'état IA ne tombe pas avec le registre
        return {"disponible": False, "motif": f"{type(e).__name__}: {e}"}
    prod = reg.production()
    candidats = reg.par_statut("candidate")
    m = (prod.manifest if prod else {}) or {}
    return {
        "disponible": True,
        "production": prod.version if prod else None,
        "dataset_hash": (m.get("dataset_hash") or "")[:16] or None,
        "git_commit": (m.get("git_commit") or "")[:12] or None,
        "feature_version": m.get("feature_version"),
        "metriques": m.get("metriques") or {},
        "entraine_le": m.get("cree_le"),
        # Un arbre git sale au moment du run signifie que ce modèle n'est PAS
        # reproductible depuis ce commit — l'information la plus utile avant
        # d'essayer de le refaire.
        "reproductible": not str(m.get("git_commit") or "").endswith("-sale"),
        "candidats": [e.version for e in candidats],
        "archives": [e.version for e in reg.archives()][:5],
        "incoherences": reg.incoherences(),
    }
