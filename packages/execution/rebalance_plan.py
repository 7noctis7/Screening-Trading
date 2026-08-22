"""Décider quoi envoyer au courtier : acheter, alléger, SOLDER, ou ne rien faire.

Cette décision était noyée dans le script d'exécution, en une seule règle symétrique :
« si |cible − détenu| < bande, ne rien faire ». Elle produit deux défauts opposés, tous deux
observés sur le compte réel.

1. LA POUSSIÈRE EST CRÉÉE PUIS PROTÉGÉE À VIE. On solde en MONTANT (« vends pour 812 $ »),
   jamais en quantité : le cours bouge entre la cotation et l'exécution, il reste une miette.
   La miette vaut alors moins que la bande — donc la sortie suivante la déclare « déjà alignée »
   et ne la vend jamais. Le compte accumule des lignes à 0,01 $ qui ne partiront plus jamais.
   Le compte réel en comptait une trentaine, pour un total d'environ 17 $ : sans effet sur la
   performance, mais elles faussent le nombre de positions, la diversification et le journal.
   Correctif : une SORTIE COMPLÈTE ne passe pas par la bande, et s'envoie en QUANTITÉ.

2. LA POUSSIÈRE EST CRÉÉE À L'OUVERTURE. Une cible minuscule ouvre quand même une ligne, qui
   deviendra la miette de demain. Correctif : sous un plancher, on n'ouvre pas — on attend que
   la cible mérite une ligne.

La bande garde tout son sens entre les deux : un écart trop petit ne paie pas son aller-retour.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

# PLANCHER DE LIGNE. Une position que la stratégie veut à moins de ce montant ne devrait pas
# exister : elle ne déplace pas le résultat, mais elle consomme du frottement, de l'attention et
# une ligne de journal. Le compte réel en comptait une quarantaine sous 500 $, dont une trentaine
# sous 3 $ — ni diversification ni performance, seulement du bruit.
#
# Réglable par QUANT_MIN_POSITION. À 1 000 $ sur un portefeuille de 100 000 $, cela revient à
# dire : « une ligne pèse au moins 1 %, sinon elle n'a pas sa place ». Seuil choisi par
# l'utilisateur — en dessous, une ligne ne déplace pas le résultat mais consomme du frottement,
# de l'attention et une ligne de journal.
MIN_LIGNE_DEFAUT = 1000.0

# HYSTÉRÉSIS. Ouvrir au-dessus du plancher mais ne solder qu'en dessous de 80 % de celui-ci crée
# une zone morte. Sans elle, une cible qui oscille autour du plancher ferait acheter et solder la
# même ligne un jour sur deux — le va-et-vient coûterait bien plus que la ligne ne rapporte.
RATIO_SORTIE = 0.8


def min_ligne() -> float:
    """Plancher de ligne effectif (QUANT_MIN_POSITION). Une valeur illisible retombe sur le
    défaut : une faute de frappe ne doit pas désactiver silencieusement le garde-fou."""
    try:
        v = float(os.environ.get("QUANT_MIN_POSITION", "") or MIN_LIGNE_DEFAUT)
        return v if v >= 0 else MIN_LIGNE_DEFAUT
    except ValueError:
        return MIN_LIGNE_DEFAUT


# Rétrocompatibilité de nom : l'ancien seuil ne servait qu'à l'ouverture.
MIN_OUVERTURE = MIN_LIGNE_DEFAUT
# Une position existe dès que le courtier la déclare — même à un centime. Aucun seuil ici : un
# epsilon « raisonnable » laisserait justement immortelles les lignes à 0,01 $ qu'on veut solder.
# La liquidation part en QUANTITÉ, donc le courtier sait fermer une fraction que son montant
# minimum d'ordre refuserait.
EPS_DETENU = 0.0


@dataclass(frozen=True)
class Intention:
    """Ce qu'on veut faire d'une ligne, et pourquoi. `liquidation` → ordre en QUANTITÉ."""
    action: str                 # "acheter" | "alleger" | "solder" | "rien"
    montant: float              # montant à échanger, toujours ≥ 0
    motif: str
    liquidation: bool = False   # True → sortie totale : envoyer la quantité, pas un montant

    @property
    def agit(self) -> bool:
        return self.action != "rien"


def decider(cible: float, detenu: float, bande: float,
            min_ouverture: float | None = None) -> Intention:
    """Décide pour UNE ligne. `cible` et `detenu` en monnaie, `bande` = seuil d'inaction.

    L'ordre des règles porte le sens : le plancher décide si la ligne DOIT EXISTER, et seulement
    ensuite la bande décide si l'écart mérite un ordre. L'inverse laisserait vivre indéfiniment
    des lignes trop petites, protégées par la bande — c'est exactement ce qui s'était produit.
    """
    plancher = min_ligne() if min_ouverture is None else float(min_ouverture)
    cible = max(0.0, float(cible))
    detenu = max(0.0, float(detenu))

    # 1. LA LIGNE A-T-ELLE SA PLACE ? Une cible sous le plancher vaut une cible NULLE. C'est le
    #    changement de fond : auparavant le plancher n'empêchait que l'ouverture, donc une ligne
    #    déjà trop petite restait pour toujours.
    if cible < plancher:
        if detenu <= EPS_DETENU:
            return Intention("rien", 0.0,
                             f"cible {cible:.0f} sous le plancher de ligne ({plancher:.0f}) "
                             "— on n'ouvre pas ce qui deviendrait de la poussière")
        # Hystérésis : on ne solde qu'en dessous de 80 % du plancher, pour qu'une cible qui
        # oscille autour du seuil ne fasse pas acheter puis solder la même ligne en boucle.
        if cible > plancher * RATIO_SORTIE:
            return Intention("rien", 0.0,
                             f"cible {cible:.0f} dans la zone morte du plancher "
                             f"({plancher * RATIO_SORTIE:.0f}–{plancher:.0f}) — on ne fait rien")
        motif = ("sortie complète — la bande ne s'applique pas à une liquidation, "
                 "sinon le résidu est immortel" if cible <= 0.0 else
                 f"cible {cible:.0f} sous le plancher de ligne ({plancher:.0f}) "
                 "— cette ligne ne pèse rien et coûte du frottement")
        return Intention("solder", detenu, motif, liquidation=True)

    # 2. BANDE D'INACTION — la ligne a sa place ; l'écart paie-t-il son aller-retour ?
    delta = cible - detenu
    if abs(delta) < bande:
        return Intention("rien", 0.0, "écart sous la bande d'inaction")

    return (Intention("acheter", delta, "sous-pondéré") if delta > 0
            else Intention("alleger", -delta, "sur-pondéré"))


def plan(cibles: dict[str, float], detenus: dict[str, float], bande: float,
         min_ouverture: float | None = None) -> dict[str, Intention]:
    """Plan complet. Toute ligne DÉTENUE hors cibles est traitée comme une cible à zéro —
    c'est ce qui garantit qu'aucune position ne peut se cacher du rééquilibrage."""
    clefs = set(cibles) | set(detenus)
    return {k: decider(cibles.get(k, 0.0), detenus.get(k, 0.0), bande, min_ouverture)
            for k in sorted(clefs)}


def poussiere(detenus: dict[str, float], seuil: float | None = None) -> dict[str, float]:
    """Lignes résiduelles : détenues, mais trop petites pour compter. Diagnostic pur."""
    s = min_ligne() if seuil is None else float(seuil)
    return {k: v for k, v in detenus.items() if EPS_DETENU < v < s}
