"""Disjoncteur du fournisseur LLM — trois états, et une raison d'exister.

À NE PAS CONFONDRE avec `packages.execution.coupe_circuit`, qui surveille la perte du JOUR
et peut fermer des positions. Celui-ci ne protège que du TEMPS PERDU : quand LM Studio est
éteint, chaque appel attend son délai avant d'échouer. Sur deux cents titres et cinq
secondes de délai, cela fait dix-sept minutes à ne rien faire — et pendant ce temps, le
reste de l'analyse attend.

    CLOSED      on appelle normalement
    OPEN        le fournisseur a échoué N fois de suite : on rend un repli IMMÉDIATEMENT,
                sans appeler, pendant une durée de refroidissement
    HALF_OPEN   le refroidissement est écoulé : on laisse passer UN seul appel d'essai.
                Succès → CLOSED. Échec → OPEN à nouveau, sans rafale de tentatives.

POURQUOI UN SEUL ESSAI EN HALF_OPEN. Rouvrir en grand après une panne envoie deux cents
requêtes vers un service qui vient peut-être à peine de redémarrer — on le fait retomber
avec la charge qu'on lui envoie pour vérifier qu'il tient. Un essai suffit à trancher.

Aucun état n'est persisté : un disjoncteur qui survit au processus décrit l'état d'un
service tel qu'il était à l'arrêt précédent, ce qui n'apprend rien sur maintenant.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field

FERME = "CLOSED"
OUVERT = "OPEN"
ENTROUVERT = "HALF_OPEN"

SEUIL_ECHECS = 3          # échecs CONSÉCUTIFS avant ouverture
REFROIDISSEMENT_S = 60.0  # avant de retenter une fois


@dataclass
class Disjoncteur:
    """Compte les échecs consécutifs. Sûr en accès concurrent : le moteur NLP appelle
    plusieurs titres en parallèle, et un compteur non protégé raterait des échecs."""

    seuil: int = SEUIL_ECHECS
    refroidissement_s: float = REFROIDISSEMENT_S
    _etat: str = FERME
    _echecs: int = 0
    _ouvert_depuis: float = 0.0
    _essai_en_cours: bool = False
    _verrou: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _horloge: object = field(default=time.monotonic, repr=False)

    def etat(self) -> str:
        """État COURANT — le refroidissement est évalué à la lecture, pas par un minuteur."""
        with self._verrou:
            return self._etat_verrouille()

    def _etat_verrouille(self) -> str:
        if self._etat == OUVERT and self._ecoule() >= self.refroidissement_s:
            self._etat = ENTROUVERT
            self._essai_en_cours = False
        return self._etat

    def _ecoule(self) -> float:
        return float(self._horloge()) - self._ouvert_depuis  # type: ignore[operator]

    def autorise(self) -> bool:
        """Peut-on appeler le fournisseur maintenant ?"""
        with self._verrou:
            etat = self._etat_verrouille()
            if etat == FERME:
                return True
            if etat == OUVERT:
                return False
            # ENTROUVERT : un seul essai à la fois, les autres repartent en repli.
            if self._essai_en_cours:
                return False
            self._essai_en_cours = True
            return True

    def succes(self) -> None:
        with self._verrou:
            self._etat = FERME
            self._echecs = 0
            self._essai_en_cours = False

    def echec(self) -> None:
        with self._verrou:
            self._essai_en_cours = False
            if self._etat == ENTROUVERT:
                # L'essai a échoué : on rouvre pour un cycle complet, sans rafale.
                self._ouvrir()
                return
            self._echecs += 1
            if self._echecs >= self.seuil:
                self._ouvrir()

    def _ouvrir(self) -> None:
        self._etat = OUVERT
        self._ouvert_depuis = float(self._horloge())  # type: ignore[operator]
        self._echecs = self.seuil

    def reinitialiser(self) -> None:
        """Remise à zéro explicite — pour les tests et un redémarrage manuel de service."""
        with self._verrou:
            self._etat, self._echecs = FERME, 0
            self._ouvert_depuis, self._essai_en_cours = 0.0, False

    def etat_public(self) -> dict:
        """Ce que `/api/ai/status` doit pouvoir montrer."""
        with self._verrou:
            etat = self._etat_verrouille()
            reste = (max(0.0, self.refroidissement_s - self._ecoule())
                     if etat == OUVERT else 0.0)
            return {"etat": etat, "echecs_consecutifs": self._echecs,
                    "reouverture_dans_s": round(reste, 1)}
