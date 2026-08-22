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

from dataclasses import dataclass

# Plancher d'ouverture : sous ce montant, une ligne coûte plus en frottement et en attention
# qu'elle n'apporte en diversification. Volontairement bas — il écarte la poussière, pas une
# position modeste assumée.
MIN_OUVERTURE = 25.0
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
            min_ouverture: float = MIN_OUVERTURE) -> Intention:
    """Décide pour UNE ligne. `cible` et `detenu` en monnaie, `bande` = seuil d'inaction.

    L'ordre des règles porte le sens : solder prime sur la bande, la bande prime sur le plancher.
    """
    cible = max(0.0, float(cible))
    detenu = max(0.0, float(detenu))
    delta = cible - detenu

    # 1. SORTIE COMPLÈTE — hors bande, toujours. C'est la règle qui empêche la poussière de
    #    devenir permanente : sans elle, tout résidu sous la bande est immortel.
    if cible <= 0.0:
        if detenu <= EPS_DETENU:
            return Intention("rien", 0.0, "aucune position à solder")
        return Intention("solder", detenu, "sortie complète — la bande ne s'applique pas "
                                           "à une liquidation, sinon le résidu est immortel",
                         liquidation=True)

    # 2. OUVERTURE SOUS LE PLANCHER — ne pas créer la poussière de demain.
    if detenu <= EPS_DETENU and cible < min_ouverture:
        return Intention("rien", 0.0,
                         f"cible {cible:.2f} sous le plancher d'ouverture ({min_ouverture:.0f})")

    # 3. BANDE D'INACTION — l'écart ne paie pas son aller-retour.
    if abs(delta) < bande:
        return Intention("rien", 0.0, "écart sous la bande d'inaction")

    return (Intention("acheter", delta, "sous-pondéré") if delta > 0
            else Intention("alleger", -delta, "sur-pondéré"))


def plan(cibles: dict[str, float], detenus: dict[str, float], bande: float,
         min_ouverture: float = MIN_OUVERTURE) -> dict[str, Intention]:
    """Plan complet. Toute ligne DÉTENUE hors cibles est traitée comme une cible à zéro —
    c'est ce qui garantit qu'aucune position ne peut se cacher du rééquilibrage."""
    clefs = set(cibles) | set(detenus)
    return {k: decider(cibles.get(k, 0.0), detenus.get(k, 0.0), bande, min_ouverture)
            for k in sorted(clefs)}


def poussiere(detenus: dict[str, float], seuil: float = MIN_OUVERTURE) -> dict[str, float]:
    """Lignes résiduelles : détenues, mais trop petites pour compter. Diagnostic pur."""
    return {k: v for k, v in detenus.items() if EPS_DETENU < v < seuil}
