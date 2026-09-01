"""DDM — dimensionnement dynamique en unités R, machine à états sur le drawdown.

SPÉCIFIÉ PAR L'UTILISATEUR (01/09). Trois niveaux de risque, descente géométrique sur
les pertes, remontée ASYMÉTRIQUE sur les gains, plus un disjoncteur journalier.

    DD0  R = 1,00 % de l'equity      ← niveau de base
    DD1  R = 0,50 %                  ← après 4 pertes consécutives OU −4R cumulés
    DD2  R = 0,25 %                  ← idem sous le régime DD1

    remontée : 4 gains consécutifs OU +4R nets AU NIVEAU COURANT

CE QUE CE MODULE FAIT ET NE FAIT PAS. Il réduit la dispersion de l'equity et le risque
de ruine. Il ne crée AUCUN avantage : réduire la taille réduit proportionnellement les
gains et les pertes, donc l'espérance PAR UNITÉ DE RISQUE est inchangée. Sur une
stratégie à profit factor 1,01, le DDM rend la courbe plus lisse, pas rentable.

RELATION AVEC L'EXISTANT. `risk/convex_drawdown_scaler` module l'exposition en CONTINU
selon le drawdown de l'equity ; le DDM réagit en DISCRET au compte de trades. Les deux
sont composables et mesurent des choses différentes — on ne remplace pas l'un par
l'autre sans mesure.

STATUT : SHADOW. Aucun appelant en production. Le brancher est une décision explicite.

Note sur « −4R cumulés » : au niveau DD1, R vaut 0,5 % de l'equity, donc −4R vaut −2 %
et non −4 %. Le seuil se resserre à chaque descente — c'est le propre d'un désengagement
géométrique, et c'est voulu.
"""

from __future__ import annotations

from dataclasses import dataclass, field

STATUT = "SHADOW_UNCALIBRATED"


@dataclass(frozen=True)
class ReglesDDM:
    """Paramètres du DDM. Figés à l'instanciation : un réglage qui bouge en cours de
    route rendrait l'historique des niveaux ininterprétable."""

    r_base: float = 0.01                       # 1R au niveau DD0, en fraction d'equity
    facteurs: tuple[float, ...] = (1.0, 0.5, 0.25)
    pertes_pour_descendre: int = 4
    gains_pour_remonter: int = 4
    r_net_declencheur: float = 4.0             # ±4R
    perte_jour_max: float = 0.03               # disjoncteur : 3 % (fourchette 2-4 %)

    def __post_init__(self) -> None:
        if self.r_base <= 0:
            raise ValueError("r_base doit être > 0")
        if not self.facteurs or any(f <= 0 for f in self.facteurs):
            raise ValueError("facteurs doivent être > 0")
        if list(self.facteurs) != sorted(self.facteurs, reverse=True):
            raise ValueError("facteurs doivent décroître : DD0 > DD1 > DD2")
        if not 0.0 < self.perte_jour_max < 1.0:
            raise ValueError("perte_jour_max doit être dans ]0, 1[")


@dataclass
class MachineDDM:
    """État du dimensionnement. `enregistrer` prend un P&L EXPRIMÉ EN R.

    En R et non en dollars, délibérément : c'est la seule unité dans laquelle « −4R »
    garde le même sens quand l'equity et le niveau changent. Convertir en dollars à
    l'entrée introduirait une dépendance au capital que la règle ne veut pas.
    """

    regles: ReglesDDM = field(default_factory=ReglesDDM)
    niveau: int = 0
    pertes_consecutives: int = 0
    gains_consecutifs: int = 0
    r_net_au_niveau: float = 0.0
    historique: list[tuple[int, str]] = field(default_factory=list)

    @property
    def facteur(self) -> float:
        return self.regles.facteurs[self.niveau]

    def risque_fractionnaire(self) -> float:
        """R courant, en fraction de l'equity."""
        return self.regles.r_base * self.facteur

    def risque_en_devise(self, equity: float) -> float:
        """Capital à risquer sur le prochain trade."""
        return max(0.0, float(equity)) * self.risque_fractionnaire()

    def enregistrer(self, pnl_en_r: float) -> int:
        """Intègre un trade CLÔTURÉ et renvoie le nouveau niveau.

        Un P&L nul ne casse aucune série et ne compte pas : il n'est ni un gain ni une
        perte, et le traiter comme l'un des deux fausserait les deux compteurs.
        """
        p = float(pnl_en_r)
        if p == 0.0:
            return self.niveau
        self.r_net_au_niveau += p
        if p < 0:
            self.pertes_consecutives += 1
            self.gains_consecutifs = 0
        else:
            self.gains_consecutifs += 1
            self.pertes_consecutives = 0
        return self._transition()

    def _transition(self) -> int:
        r = self.regles
        descend = (self.pertes_consecutives >= r.pertes_pour_descendre
                   or self.r_net_au_niveau <= -r.r_net_declencheur)
        monte = (self.gains_consecutifs >= r.gains_pour_remonter
                 or self.r_net_au_niveau >= r.r_net_declencheur)
        if descend and self.niveau < len(r.facteurs) - 1:
            return self._changer(self.niveau + 1, "descente")
        if monte and self.niveau > 0:
            return self._changer(self.niveau - 1, "remontée")
        return self.niveau

    def _changer(self, niveau: int, motif: str) -> int:
        """Tout compteur repart à zéro au changement de niveau.

        Sans cette remise à zéro, les −4R accumulés à DD0 continueraient de compter à
        DD1 et provoqueraient une seconde descente immédiate — le système tomberait à
        DD2 sur un seul épisode de pertes.
        """
        self.niveau = niveau
        self.pertes_consecutives = 0
        self.gains_consecutifs = 0
        self.r_net_au_niveau = 0.0
        self.historique.append((niveau, motif))
        return niveau

    def etat(self) -> dict:
        """Observabilité : ce que la machine ferait, et pourquoi."""
        return {
            "statut": STATUT,
            "niveau": self.niveau,
            "libelle": f"DD{self.niveau}",
            "facteur": self.facteur,
            "risque_pct": round(self.risque_fractionnaire() * 100, 4),
            "pertes_consecutives": self.pertes_consecutives,
            "gains_consecutifs": self.gains_consecutifs,
            "r_net_au_niveau": round(self.r_net_au_niveau, 4),
            "transitions": len(self.historique),
        }


def taille_position(equity: float, entree: float, stop: float,
                    machine: MachineDDM) -> float:
    """Quantité à acheter/vendre = capital risqué / distance au stop.

    Renvoie 0 plutôt que de lever quand la distance au stop est nulle ou aberrante : un
    stop collé au prix d'entrée donnerait une taille infinie, et c'est exactement le
    genre de division silencieuse qui ruine un compte.
    """
    distance = abs(float(entree) - float(stop))
    if distance <= 0 or equity <= 0:
        return 0.0
    return machine.risque_en_devise(equity) / distance
