"""Market Intelligence — collecte, qualification et pondération de l'information de marché.

Cette couche ALIMENTE l'analyse. Elle n'émet aucun ordre, ne connaît aucun courtier, et
n'importe rien de `packages.execution` : la séparation est structurelle, pas conventionnelle.

Chaîne : source → authentification → score de source → nature (fait/opinion/rumeur) →
corroboration croisée → pertinence → statut exploitable ou non.
"""

from packages.intelligence.classify import (
                                            EXPLOITABLES,
                                            Classement,
                                            Information,
                                            Nature,
                                            Statut,
                                            classer,
)
from packages.intelligence.corroboration import Bilan, Rapport, croiser
from packages.intelligence.relevance import Categorie, Pertinence, categoriser
from packages.intelligence.relevance import evaluer as evaluer_pertinence
from packages.intelligence.sources import (
                                            Niveau,
                                            ScoreSource,
                                            Source,
                                            score_source,
                                            utilisable_seule,
)
from packages.intelligence.watchlist import (
                                            WATCHLIST,
                                            Candidat,
                                            a_verifier,
                                            en_source,
                                            resume,
)

__all__ = ["EXPLOITABLES", "Bilan", "Candidat", "Categorie", "Classement", "Information",
           "Nature", "Niveau", "Pertinence", "Rapport", "ScoreSource", "Source", "Statut",
           "WATCHLIST", "a_verifier", "categoriser", "classer", "croiser", "en_source",
           "evaluer_pertinence", "resume", "score_source", "utilisable_seule"]
