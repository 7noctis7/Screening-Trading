"""Classer une information : fait, opinion, rumeur — et ne jamais les confondre.

Le mécanisme par lequel un pipeline d'intelligence de marché devient dangereux est toujours le
même : une opinion d'investisseur reconnu entre dans le système, traverse quelques couches, et
en ressort comme une donnée. Le typage explicite est la seule protection.

Deux règles inviolables, encodées ici plutôt que laissées à la discipline de l'appelant :

  1. Une OPINION, une PRÉDICTION ou une SPÉCULATION ne peut JAMAIS devenir un FAIT, quelle que
     soit la qualité de la source. Une excellente source qui donne son avis donne un avis.
  2. Une affirmation factuelle non corroborée reste UNCONFIRMED. Seules une source primaire
     authentifiée, ou une corroboration indépendante suffisante, la font passer à CONFIRMED.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from packages.intelligence.sources import Source, utilisable_seule


class Nature(StrEnum):
    """Ce que l'énoncé PRÉTEND être — déterminé à la lecture, avant toute pondération."""
    FACTUELLE = "factuelle"        # affirme un état du monde vérifiable
    OPINION = "opinion"            # jugement de valeur
    PREDICTION = "prediction"      # affirme un état FUTUR
    RUMEUR = "rumeur"              # rapporte un dire non sourcé


class Statut(StrEnum):
    """Ce que le système est prêt à en faire. Seuls FACT et CONFIRMED sont exploitables comme
    une donnée ; tout le reste doit rester étiqueté jusqu'au bout de la chaîne."""
    FACT = "FACT"                  # source primaire authentifiée, énoncé factuel
    CONFIRMED = "CONFIRMED"        # factuel + corroboration indépendante suffisante
    PROBABLE = "PROBABLE"          # factuel + corroboration partielle
    UNCONFIRMED = "UNCONFIRMED"    # factuel, aucune corroboration
    RUMOR = "RUMOR"
    OPINION = "OPINION"
    SPECULATION = "SPECULATION"    # prédiction


# Un statut exploitable comme une DONNÉE. Le reste alimente l'analyse, jamais un calcul.
EXPLOITABLES = frozenset({Statut.FACT, Statut.CONFIRMED})


@dataclass(frozen=True)
class Information:
    """Une information collectée, avant classement."""
    texte: str
    source: Source
    nature: Nature
    url: str = ""
    horodatage: str = ""
    sujet: str = ""
    actifs: tuple[str, ...] = ()
    impact_potentiel: str = "faible"      # faible | moyen | fort — pilote l'exigence de preuve


@dataclass(frozen=True)
class Classement:
    statut: Statut
    motif: str
    exploitable: bool


def classer(info: Information, corroborations: int = 0,
            corroboration_primaire: bool = False) -> Classement:
    """Statut d'une information. `corroborations` = nombre de sources INDÉPENDANTES concordantes.

    L'exigence monte avec l'impact : une information à fort impact demande davantage qu'une
    brève sectorielle. C'est délibéré — le coût d'une erreur n'est pas le même.
    """
    if info.nature is Nature.OPINION:
        return Classement(Statut.OPINION, "jugement de valeur — jamais un fait", False)
    if info.nature is Nature.PREDICTION:
        return Classement(Statut.SPECULATION, "affirme un état futur — invérifiable aujourd'hui",
                          False)
    if info.nature is Nature.RUMEUR:
        if corroboration_primaire:
            return Classement(Statut.CONFIRMED,
                              "rumeur confirmée par une source primaire authentifiée", True)
        return Classement(Statut.RUMOR, "rapport non sourcé — détection uniquement", False)

    # --- énoncé FACTUEL ---
    if utilisable_seule(info.source):
        return Classement(Statut.FACT, "source primaire authentifiée", True)
    requis = {"fort": 3, "moyen": 2}.get(info.impact_potentiel, 1)
    if corroboration_primaire:
        return Classement(Statut.CONFIRMED, "corroboré par une source primaire", True)
    if corroborations >= requis:
        return Classement(Statut.CONFIRMED,
                          f"{corroborations} sources indépendantes ≥ {requis} requis", True)
    if corroborations >= 1:
        return Classement(Statut.PROBABLE,
                          f"{corroborations} source(s) sur {requis} requis pour cet impact", False)
    return Classement(Statut.UNCONFIRMED,
                      f"aucune corroboration ({requis} requis pour un impact "
                      f"{info.impact_potentiel})", False)
