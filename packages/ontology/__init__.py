"""Ontologie — les OBJETS MÉTIERS du domaine et leurs relations (colonne vertébrale Karp).

Le snapshot expose ~23 sections plates ; l'utilisateur pense en 7 objets : Instrument,
Signal/Hypothèse, Verdict de gate, Régime, Portefeuille, Position/Round-trip, Note.
Cette couche NE CALCULE RIEN de neuf (Musk : zéro pièce superflue) : elle RÉSOUT un objet
par id en re-projetant les sections déjà en cache → un seul endpoint générique
`/api/object/{type}/{id}` au lieu d'un hook front par table.

Extension = 1 résolveur enregistré (pattern plugin, comme `core/registry`). Honnêteté :
section absente → relation `available: False`, jamais de valeur inventée.
"""

from packages.ontology.resolve import OBJECT_TYPES, resolve

__all__ = ["OBJECT_TYPES", "resolve"]
