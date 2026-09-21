"""Cycle de vie d'un travail de calcul — et l'interdiction qu'une machine reste allumée.

CE QUE CE MODULE DÉFINIT, ET PAS OÙ ÇA TOURNE. `ComputeBackend` ne sait pas s'il parle à un
sous-processus local, à un GPU loué ou à un cluster. Le pipeline dépose un travail, demande
son état, récupère ses artefacts, l'arrête. Coupler le cœur du projet à un fournisseur
serait le rendre otage d'une facture — et rendre impossible d'en changer le jour où le prix
double.

LA DOUBLE PROTECTION, ET POURQUOI LA SECONDE EST LA SEULE QUI COMPTE

    Protection 1 — APPLICATIVE. Le superviseur arrête la machine dans un `finally` :
    travail fini, échoué, expiré, exception inattendue, tout passe par là.

    Protection 2 — INFRASTRUCTURE. Un `max_runtime_s` posé SUR LA MACHINE à sa création,
    honoré par le fournisseur lui-même.

La première suffit tant que le superviseur tourne. Elle ne sert à rien quand c'est LUI qui
meurt — coupure réseau, processus tué, machine locale éteinte — et c'est précisément le
scénario qui laisse une instance GPU facturer pendant une semaine. `Travail` exige donc
`max_runtime_s` : un backend qui ne sait pas l'imposer doit le DIRE plutôt que l'ignorer.

CE QU'UN TRAVAIL NE PEUT PAS FAIRE. Passer un ordre, modifier une limite de risque, activer
le mode réel. `packages/mlops` n'atteint aucun chemin d'exécution — vérifié sur le graphe
d'imports — et cette interface n'expose aucun moyen de contourner cela.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol, runtime_checkable

EN_ATTENTE = "en_attente"
EN_COURS = "en_cours"
REUSSI = "reussi"
ECHOUE = "echoue"
EXPIRE = "expire"
ARRETE = "arrete"
ETATS_FINAUX = (REUSSI, ECHOUE, EXPIRE, ARRETE)

MAX_RUNTIME_DEFAUT_S = 3600.0     # une heure : au-delà, c'est un choix, pas un oubli


def _duree(s: float | None) -> str:
    """Durée LISIBLE. « 0 s » pour un plafond d'une demi-seconde rendait le message absurde
    — « durée 1 s > plafond 0 s » — et une comparaison illisible ne se vérifie pas."""
    if s is None:
        return "—"
    if s < 10:
        return f"{s:.2f} s"
    if s < 600:
        return f"{s:.0f} s"
    return f"{s / 60:.0f} min"


@dataclass(frozen=True)
class Travail:
    """Ce qu'on demande. `max_runtime_s` n'a PAS de valeur « illimitée », par construction."""

    experience: str                       # ex. « EXP-2026-09-001 »
    commande: list[str]                   # argv, jamais une chaîne shell — cf. plus bas
    max_runtime_s: float = MAX_RUNTIME_DEFAUT_S
    artefacts_attendus: tuple[str, ...] = ()
    env: dict[str, str] = field(default_factory=dict)
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    cree_le: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def __post_init__(self) -> None:
        if not self.commande:
            raise ValueError("un travail sans commande ne calcule rien")
        if self.max_runtime_s <= 0:
            raise ValueError("max_runtime_s doit être > 0 — il n'existe pas d'illimité ici")
        # Une chaîne shell laisserait un manifeste distant injecter « ; rm -rf ». `argv`
        # rend l'injection structurellement impossible : pas de shell, pas d'interprétation.
        if any(not isinstance(a, str) for a in self.commande):
            raise ValueError("la commande doit être une liste d'arguments (argv)")
        # Un secret passé en argument apparaît dans `ps` de toute machine partagée.
        for a in self.commande:
            if any(m in a.upper() for m in ("API_KEY=", "SECRET=", "TOKEN=", "PASSWORD=")):
                raise ValueError("secret dans la ligne de commande — passer par `env`")


@dataclass
class EtatTravail:
    """Où en est un travail. `cout_usd` reste `None` tant qu'il n'est pas CONNU."""

    travail_id: str
    etat: str = EN_ATTENTE
    debut: str | None = None
    fin: str | None = None
    code_sortie: int | None = None
    message: str = ""
    runtime_s: float | None = None
    materiel: str | None = None
    cout_usd: float | None = None
    artefacts: tuple[str, ...] = ()

    @property
    def termine(self) -> bool:
        return self.etat in ETATS_FINAUX

    @property
    def reussi(self) -> bool:
        return self.etat == REUSSI

    def en_dict(self) -> dict:
        return {**self.__dict__, "artefacts": list(self.artefacts)}


@runtime_checkable
class ComputeBackend(Protocol):
    """Volontairement minuscule : cinq verbes, et `terminer` doit être IDEMPOTENT."""

    nom: str

    def soumettre(self, travail: Travail) -> EtatTravail: ...
    def etat(self, travail_id: str) -> EtatTravail: ...
    def recuperer(self, travail_id: str, vers: Path) -> list[Path]: ...
    def terminer(self, travail_id: str, motif: str = "") -> bool: ...
    def impose_max_runtime(self) -> bool: ...
    def cout_estime(self, runtime_s: float) -> float | None: ...


class Superviseur:
    """Exécute le cycle complet et GARANTIT l'arrêt — c'est sa seule raison d'exister.

    Le `finally` n'est pas une précaution de style : c'est la protection 1. Sans lui, une
    exception entre « entraînement fini » et « artefacts récupérés » laisserait la machine
    allumée, et l'erreur remontée masquerait complètement la facture qui court.
    """

    def __init__(self, backend: ComputeBackend, magasin=None):
        self.backend = backend
        self.magasin = magasin
        self.avertissements: list[str] = []

    def executer(self, travail: Travail, vers: Path) -> EtatTravail:
        if not self.backend.impose_max_runtime():
            # On N'INTERDIT pas — un backend local n'a pas de facture. On le DIT, parce
            # qu'un défaut de protection silencieux est ce qui coûte cher chez un loueur.
            self.avertissements.append(
                f"{self.backend.nom} n'impose pas de plafond de durée côté infrastructure : "
                "seule la protection applicative joue. À ne pas utiliser pour du GPU facturé.")
        etat = self.backend.soumettre(travail)
        try:
            etat = self._attendre(travail)
            if etat.reussi:
                etat = self._recolter(travail, etat, vers)
            return etat
        except BaseException as e:  # noqa: BLE001 — y compris KeyboardInterrupt
            self.avertissements.append(f"interruption : {type(e).__name__}: {e}")
            raise
        finally:
            # PROTECTION 1 — quoi qu'il arrive au-dessus.
            self.backend.terminer(travail.id, "fin de supervision")

    def _attendre(self, travail: Travail) -> EtatTravail:
        etat = self.backend.etat(travail.id)
        if not etat.termine:
            etat = self.backend.etat(travail.id)
        # PLAFOND, VERSION SUPERVISEUR. Il ne s'applique que si le backend n'a PAS déjà
        # détecté l'expiration : écraser son verdict remplacerait « processus tué à
        # l'échéance » — ce qui dit CE QUI s'est passé — par une comparaison de durées.
        depasse = etat.runtime_s is not None and etat.runtime_s > travail.max_runtime_s
        if depasse and etat.etat != EXPIRE:
            self.backend.terminer(travail.id, "plafond de durée dépassé")
            etat.etat, etat.message = EXPIRE, (
                f"durée {_duree(etat.runtime_s)} > plafond "
                f"{_duree(travail.max_runtime_s)} — arrêté par le superviseur")
        if etat.cout_usd is None and etat.runtime_s is not None:
            etat.cout_usd = self.backend.cout_estime(etat.runtime_s)
        return etat

    def _recolter(self, travail: Travail, etat: EtatTravail, vers: Path) -> EtatTravail:
        """Récupère et VÉRIFIE avant de déclarer le succès.

        Un travail dont le processus sort en 0 mais n'a rien produit n'est pas un succès :
        c'est un échec silencieux, le plus coûteux de tous puisqu'il promeut du vide.
        """
        fichiers = self.backend.recuperer(travail.id, vers)
        noms = {Path(f).name for f in fichiers}
        manquants = [a for a in travail.artefacts_attendus if Path(a).name not in noms]
        if manquants:
            etat.etat = ECHOUE
            etat.message = f"artefacts attendus absents : {', '.join(manquants)}"
            return etat
        etat.artefacts = tuple(str(f) for f in fichiers)
        if self.magasin is not None:
            for f in fichiers:
                self.magasin.deposer(f"{travail.experience}/{Path(f).name}", Path(f))
        return etat
