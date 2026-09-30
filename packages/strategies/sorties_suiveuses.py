"""Stops suiveurs et prise de gains PARTIELLE pour les lignes du portefeuille (overlay).

LE MANQUE. Le portefeuille qui trade (`preset_latest_weights_explique`) ne sort d'une
ligne QUE par rééquilibrage : aucune perte n'est coupée entre deux décisions, aucun gain
n'est encaissé. Ce module fournit les briques de sortie, ligne par ligne ; le rejeu
(`backtest/rejeu_sorties.py`) les mesure sur les décisions de production.

CE QUE L'HISTOIRE DU DÉPÔT IMPOSE DE DIRE D'ABORD (ADR-0052). Sur la stratégie swing, un
suiveur à 5 ATR a été mesuré sur 786 titres puis RETIRÉ : Sharpe 0,53 sans lui, 0,38 avec,
maxDD non amélioré. L'avantage vivait dans la queue droite et le suiveur la tronquait.
Rien ne dit que le portefeuille se comporte autrement ; c'est à mesurer, pas à supposer.
Statut : SHADOW_UNCALIBRATED, aucun appelant en production.

DEUX RÈGLES DE STOP (registre `REGLES`, une fonction par règle) :
  * `atr` — Chandelier : stop = plus haut de CLÔTURE depuis l'entrée − k·ATR. La clôture
    plutôt que le plus-haut : une mèche isolée ne relève pas le stop ;
  * `structure` — le stop ne bouge que sur un invalidant STRUCTUREL (même invariant que
    `moteur_sortie`) : un creux confirmé plus haut, suivi d'un sommet confirmé. Il se pose
    un TAMPON d'ATR sous le creux, au-delà de la poche de liquidité que les balayages
    (liquidity sweeps) viennent chercher juste sous les plus-bas évidents.
PRISE PARTIELLE (option) : une fraction à la liquidité opposée — le premier sommet
confirmé au-dessus de l'entrée — jamais sous `r_cible_min` R. Jamais la totalité : c'est
la leçon de l'ADR-0052, la queue droite reste en jeu.

INVARIANTS : le stop ne recule jamais ; l'état au close `d` ne lit que les barres ≤ d ;
gap sous le stop → ouverture ; stop et cible dans la même barre → le stop.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, field

from packages.indicators.market_structure import pivots_indexes

STATUT = "SHADOW_UNCALIBRATED"


@dataclass(frozen=True)
class Barre:
    """OHLC d'une séance — seuls champs lus par les règles de sortie."""

    open: float
    high: float
    low: float
    close: float


@dataclass(frozen=True)
class Reglages:
    """Valeurs CONVENTIONNELLES, non calibrées : ATR 14 de Wilder, Chandelier à 3 ATR
    (LeBeau). Les modifier après une mesure est un nouvel essai, compté au ledger."""

    periode_atr: int = 14
    k_chandelier: float = 3.0
    pivot: int = 5
    tampon_atr: float = 0.5
    k_risque_max: float = 4.0
    r_cible_min: float = 2.0
    part_prise: float = 1.0 / 3.0
    fenetre: int = 60


@dataclass
class EtatSortie:
    """État d'UNE ligne détenue. `stop` est actif pendant la séance SUIVANTE."""

    regle: str
    entree: float
    stop_initial: float
    stop: float
    atr: float
    plus_haut: float
    cible: float | None = None
    prise_faite: bool = False
    reglages: Reglages = field(default_factory=Reglages)


def vrai_range(barre: Barre, close_prec: float) -> float:
    return max(barre.high - barre.low, abs(barre.high - close_prec),
               abs(barre.low - close_prec))


def atr_initial(barres: list[Barre], periode: int) -> float:
    """Moyenne des `periode` derniers vrais ranges — NaN si l'historique est trop court."""
    if len(barres) < periode + 1:
        return float("nan")
    trs = [vrai_range(barres[k], barres[k - 1].close)
           for k in range(len(barres) - periode, len(barres))]
    return sum(trs) / periode


def atr_suivant(atr: float, tr: float, periode: int) -> float:
    """Récurrence de Wilder : ATR_d = (ATR_{d-1}·(p−1) + TR_d) / p."""
    return (atr * (periode - 1) + tr) / periode


# ------------------------------------------------------------------ registre des règles

REGLES: dict[str, Callable[[EtatSortie, list[Barre]], float | None]] = {}


def regle(nom: str) -> Callable:
    """Enregistre une règle de stop : (état, barres ≤ d) → niveau candidat ou None."""
    def enregistrer(fn: Callable) -> Callable:
        REGLES[nom] = fn
        return fn
    return enregistrer


@regle("atr")
def _chandelier(etat: EtatSortie, barres: list[Barre]) -> float | None:
    return etat.plus_haut - etat.reglages.k_chandelier * etat.atr


def _dernier_creux(barres: list[Barre], pivot: int, *, suivi: bool) -> float | None:
    """Plus-bas du dernier creux CONFIRMÉ ; `suivi` exige un sommet confirmé après lui."""
    if len(barres) < 2 * pivot + 1:
        return None
    ih, ib = pivots_indexes(barres, len(barres) - 1, pivot)
    if not ib:
        return None
    creux = ib[-1]
    if suivi and not any(h > creux for h in ih):
        return None
    return barres[creux].low


@regle("structure")
def _structure(etat: EtatSortie, barres: list[Barre]) -> float | None:
    """Nouveau niveau SI ET SEULEMENT SI la structure l'a créé. Aucune branche ne regarde
    le prix d'entrée ni le gain courant : pas de breakeven de confort."""
    r = etat.reglages
    creux = _dernier_creux(barres[-r.fenetre:], r.pivot, suivi=True)
    return None if creux is None else creux - r.tampon_atr * etat.atr


# ------------------------------------------------------------------ cycle de vie

def _stop_initial(nom: str, barres: list[Barre], entree: float, atr: float,
                  r: Reglages) -> float:
    if nom == "atr":
        return entree - r.k_chandelier * atr
    plafond = entree - r.k_risque_max * atr                  # risque par ligne borné
    creux = _dernier_creux(barres[-r.fenetre:], r.pivot, suivi=False)
    if creux is None:
        return plafond
    niveau = creux - r.tampon_atr * atr
    return max(niveau, plafond) if niveau < entree else plafond


def _cible(barres: list[Barre], entree: float, stop: float, r: Reglages) -> float:
    """Liquidité opposée : premier sommet confirmé au-dessus de l'entrée, plancher en R."""
    plancher = entree + r.r_cible_min * (entree - stop)
    fen = barres[-r.fenetre:]
    if len(fen) < 2 * r.pivot + 1:
        return plancher
    ih, _ = pivots_indexes(fen, len(fen) - 1, r.pivot)
    au_dessus = [fen[j].high for j in ih if fen[j].high > entree]
    return max(min(au_dessus), plancher) if au_dessus else plancher


def ouvrir(nom: str, barres: list[Barre], entree: float, *,
           reglages: Reglages | None = None, prise: bool = False) -> EtatSortie | None:
    """État d'une ligne ouverte au close de la DERNIÈRE barre de `barres` (≤ jour d'achat).

    None si l'ATR n'est pas calculable : une ligne sans stop mesurable n'est pas gérée,
    plutôt que gérée avec un stop inventé."""
    if nom not in REGLES:
        raise ValueError(f"règle de sortie inconnue : {nom} (connues : {sorted(REGLES)})")
    r = reglages or Reglages()
    atr = atr_initial(barres, r.periode_atr)
    if not (math.isfinite(atr) and atr > 0 and entree > 0):
        return None
    stop = _stop_initial(nom, barres, entree, atr, r)
    return EtatSortie(regle=nom, entree=entree, stop_initial=stop, stop=stop, atr=atr,
                      plus_haut=entree, reglages=r,
                      cible=_cible(barres, entree, stop, r) if prise else None)


def avancer(etat: EtatSortie, barres: list[Barre]) -> EtatSortie:
    """Met l'état à jour au close de la dernière barre de `barres` (cliquet : jamais de
    recul). L'appelant ne passe QUE des barres ≤ d : c'est la garantie de causalité."""
    if len(barres) >= 2:
        r = etat.reglages
        etat.atr = atr_suivant(etat.atr, vrai_range(barres[-1], barres[-2].close),
                               r.periode_atr)
        etat.plus_haut = max(etat.plus_haut, barres[-1].close)
    niveau = REGLES[etat.regle](etat, barres)
    if niveau is not None and niveau > etat.stop:
        etat.stop = niveau
    return etat


def declencher(etat: EtatSortie, barre: Barre) -> tuple[str, float, float] | None:
    """(motif, prix, fraction) si la séance `barre` exécute un ordre posé la veille.

    Le stop d'abord : des barres quotidiennes ne disent pas lequel est venu en premier,
    et retenir la cible fabriquerait de la performance à partir d'une ambiguïté."""
    if barre.low <= etat.stop:
        prix = min(etat.stop, barre.open) if barre.open > 0 else etat.stop
        motif = "stop_initial" if etat.stop <= etat.stop_initial else "stop_suiveur"
        return motif, prix, 1.0
    if etat.cible is not None and not etat.prise_faite and barre.high >= etat.cible:
        return "prise", etat.cible, etat.reglages.part_prise
    return None


__all__ = ["REGLES", "STATUT", "Barre", "EtatSortie", "Reglages", "atr_initial",
           "atr_suivant", "avancer", "declencher", "ouvrir", "regle", "vrai_range"]
