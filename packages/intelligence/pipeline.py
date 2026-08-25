"""Chaîne complète : une information brute → un verdict traçable.

C'est le point d'entrée unique de la couche d'intelligence. Il assemble les quatre étages dans
l'ordre qui porte le sens :

    source → score de source → nature → corroboration croisée → pertinence → statut

L'ordre n'est pas décoratif. On qualifie D'ABORD qui parle (une source faible ne devient jamais
crédible parce que son propos est intéressant), ENSUITE ce que l'énoncé prétend être (une
opinion ne devient jamais un fait), ENSUITE seulement combien de sources indépendantes le
confirment, et EN DERNIER si cela peut déplacer un prix.

Le verdict est fait pour être LU. Chaque refus nomme l'étage qui a refusé et pourquoi.

Ce module n'importe rien de `packages.execution` : aucune information, si bien notée soit-elle,
ne peut produire un ordre depuis ici.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from packages.intelligence.classify import (
    EXPLOITABLES,
    Classement,
    Information,
    classer,
)
from packages.intelligence.corroboration import Bilan, Rapport, croiser
from packages.intelligence.relevance import Pertinence
from packages.intelligence.relevance import evaluer as evaluer_pertinence
from packages.intelligence.sources import ScoreSource, score_source

# Un énoncé exploitable dont la source est faible reste une information faible : le produit des
# deux est ce qui compte. Seuil bas, mais non nul — sous 0,25 on ne construit rien de sérieux.
CONFIANCE_MIN = 0.25


@dataclass(frozen=True)
class Verdict:
    """Ce que le système retient d'une information, et pourquoi."""
    exploitable: bool
    confiance: float
    classement: Classement
    source: ScoreSource
    pertinence: Pertinence
    corroboration: Bilan
    motifs: list[str] = field(default_factory=list)

    def rapport(self) -> str:
        """Fiche lisible — le format demandé pour une synthèse de veille."""
        c = self.classement
        lignes = [
            f"statut        : {c.statut.value} ({'exploitable' if self.exploitable else 'NON exploitable'})",
            f"confiance     : {self.confiance:.0%}",
            f"source        : {self.source.valeur:.2f}",
            f"pertinence    : {self.pertinence.score:.2f} "
            f"[{', '.join(x.value for x in self.pertinence.categories)}]",
            f"corroboration : {self.corroboration.independantes} source(s) indépendante(s)"
            + (" · source primaire présente" if self.corroboration.primaire else ""),
            f"motif         : {c.motif}",
        ]
        if self.corroboration.ecartees:
            lignes.append("écartées      : " + " · ".join(self.corroboration.ecartees[:4]))
        if self.motifs:
            lignes.append("refus         : " + " · ".join(self.motifs))
        return "\n".join(lignes)


def qualifier(info: Information, reprises: list[Rapport] | None = None,
              domaine: str = "") -> Verdict:
    """Passe une information par les quatre étages. Ne lève jamais : un verdict négatif est
    un résultat, pas une erreur."""
    sc = score_source(info.source, domaine or (info.sujet or ""))
    bilan = croiser(reprises or [])
    cl = classer(info, corroborations=bilan.independantes,
                 corroboration_primaire=bilan.primaire)
    pert = evaluer_pertinence(info.texte, info.impact_potentiel, info.actifs)

    # La confiance combine QUI parle et CE QUE ça vaut — un produit, pas une moyenne : un zéro
    # sur l'un des deux doit annuler l'ensemble, et une moyenne le masquerait.
    confiance = round(sc.valeur * pert.score, 3)

    motifs: list[str] = []
    if cl.statut not in EXPLOITABLES:
        motifs.append(f"statut {cl.statut.value} — {cl.motif}")
    if not pert.retenue:
        motifs.append(f"pertinence insuffisante ({pert.score:.2f})")
    if confiance < CONFIANCE_MIN:
        motifs.append(f"confiance {confiance:.2f} < {CONFIANCE_MIN}")

    return Verdict(exploitable=not motifs, confiance=confiance, classement=cl,
                   source=sc, pertinence=pert, corroboration=bilan, motifs=motifs)
