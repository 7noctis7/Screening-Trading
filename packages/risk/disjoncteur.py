"""Disjoncteur journalier — coupe tout quand la perte du jour franchit le seuil.

SPÉCIFIÉ PAR L'UTILISATEUR (01/09), module 2.4. Compteur remis à zéro chaque jour à
00:00 UTC. Au franchissement : clôture des positions, annulation des ordres en attente,
et VERROU sur toute nouvelle entrée jusqu'au lendemain.

DEUX POINTS QUI DÉCIDENT DE LA CORRECTION, et qu'une lecture rapide de la spec rate :

1. Le seuil porte sur les pertes RÉALISÉES **ET LATENTES**. Ne compter que le réalisé
   laisserait un compte fondre sur des positions ouvertes sans jamais déclencher — le
   mode de panne exact qu'un disjoncteur existe pour empêcher.

2. Le verrou NE SE LÈVE PAS si le P&L remonte dans la journée. « Bloquer jusqu'au
   lendemain » veut dire jusqu'au lendemain. Un disjoncteur qui se réarme sur un rebond
   intrajournalier laisse rentrer précisément dans la volatilité qui l'a déclenché.

STATUT : SHADOW. Aucun appelant en production ; `execution/live_guards` porte déjà les
kill-switches actifs. Le brancher est une décision explicite.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime

STATUT = "SHADOW_UNCALIBRATED"

# Fourchette imposée par la spec : entre 2 % et 4 % de l'equity globale.
SEUIL_MIN, SEUIL_MAX = 0.02, 0.04


@dataclass
class DisjoncteurJournalier:
    """État du disjoncteur. `observer` est idempotent : l'appeler deux fois avec les
    mêmes chiffres ne déclenche pas deux fois."""

    seuil: float = 0.03
    jour: date | None = None
    perte_jour: float = 0.0
    verrouille: bool = False
    declenchements: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not SEUIL_MIN <= self.seuil <= SEUIL_MAX:
            raise ValueError(
                f"seuil {self.seuil} hors de la fourchette imposée "
                f"[{SEUIL_MIN}, {SEUIL_MAX}] — un disjoncteur trop lâche ne protège "
                "rien, trop serré coupe sur le bruit")

    def observer(self, maintenant: datetime, equity: float,
                 pnl_realise: float, pnl_latent: float = 0.0) -> dict:
        """Met à jour l'état et renvoie la décision à appliquer."""
        self._peut_etre_nouveau_jour(maintenant)
        perte = -(float(pnl_realise) + float(pnl_latent))     # >0 = on perd
        self.perte_jour = max(self.perte_jour, perte)
        limite = max(0.0, float(equity)) * self.seuil
        if not self.verrouille and limite > 0 and perte >= limite:
            self.verrouille = True
            self.declenchements.append(maintenant.isoformat())
        return self.decision(limite)

    def _peut_etre_nouveau_jour(self, maintenant: datetime) -> None:
        """Bascule de jour en UTC. Un `datetime` naïf est REFUSÉ plutôt que supposé
        UTC : un décalage de fuseau déplacerait la remise à zéro de plusieurs heures,
        et le verrou sauterait au mauvais moment."""
        if maintenant.tzinfo is None:
            raise ValueError("horodatage naïf : fournir un datetime avec fuseau (UTC)")
        j = maintenant.astimezone(UTC).date()
        if self.jour != j:
            self.jour = j
            self.perte_jour = 0.0
            self.verrouille = False

    def decision(self, limite: float | None = None) -> dict:
        return {
            "statut": STATUT,
            "verrouille": self.verrouille,
            "jour": self.jour.isoformat() if self.jour else None,
            "perte_jour": round(self.perte_jour, 2),
            "limite": round(limite, 2) if limite is not None else None,
            "fermer_positions": self.verrouille,
            "annuler_ordres": self.verrouille,
            "entrees_autorisees": not self.verrouille,
            "motif": (f"perte du jour {self.perte_jour:.2f} ≥ seuil "
                      f"{self.seuil:.1%} de l'equity" if self.verrouille else ""),
        }

    def entrees_autorisees(self) -> bool:
        return not self.verrouille
