"""LA convention de coût d'exécution — une seule dans tout le dépôt.

POURQUOI CE MODULE EXISTE. Trois endroits calculaient déjà un écart prix/prix :
`tca.implementation_shortfall`, `research.exec_costs.measured_slippage` et le repli
implicite de `costs.CostModel`. Trois formules pour une seule notion finissent par
diverger sans que rien ne le signale. Ici, une seule — et un test interdit d'en écrire
une quatrième.

LA CONVENTION. Positif = défavorable, quel que soit le sens :

    achat  : (fill − référence) / référence × 10 000
    vente  : (référence − fill) / référence × 10 000

CE QUI SE RETRANCHE, ET CE QUI NE SE RETRANCHE PAS. Le shortfall est déjà contenu dans
le prix de fill : le retrancher du P&L compterait deux fois le même coût. Mesuré le
09/09 sur le journal réel : 51 fills uniques portent les deux prix, donc 51 occasions
de faire l'erreur. Seule la commission est une charge — voir `Fill.charge`.
"""

from __future__ import annotations

from packages.core.models import Fill, Order, Side

SOURCES = ("observed", "estimated")


def shortfall_bps(reference_price: float | None, fill_price: float,
                  side: Side) -> float | None:
    """Écart d'exécution en points de base. `None` si la référence est inutilisable.

    Renvoyer 0.0 sans référence dirait « exécution parfaite » là où il faut lire
    « non mesuré » — c'est la règle n°4 du projet (jamais d'inconnu transformé en zéro).
    """
    if reference_price is None or reference_price <= 0 or fill_price <= 0:
        return None
    ecart = (fill_price - reference_price) / reference_price
    if side is Side.SHORT:
        ecart = -ecart
    return ecart * 1e4


def fill_de_l_ordre(order: Order, *, fill_price: float,
                    reference_price: float | None = None,
                    commission: float = 0.0, fees_other: float = 0.0,
                    qty: float | None = None, currency: str = "USD",
                    source: str = "estimated") -> Fill:
    """Construit le `Fill` d'un ordre exécuté. Seul point d'entrée légitime.

    `source` est validée ici plutôt qu'à la lecture : une troisième valeur qui se
    glisserait silencieusement entre « observé » et « estimé » rendrait tout le
    contrat inutile — on ne saurait plus quels chiffres viennent du courtier.
    """
    if source not in SOURCES:
        raise ValueError(f"source doit être l'une de {SOURCES}, reçu {source!r}")
    return Fill(
        instrument=order.instrument, side=order.side,
        qty=float(qty if qty is not None else order.qty),
        fill_price=float(fill_price), reference_price=reference_price,
        commission=float(commission), fees_other=float(fees_other),
        shortfall_bps=shortfall_bps(reference_price, fill_price, order.side),
        currency=currency, source=source)


def charge_du_roundtrip(entree: Fill | None, sortie: Fill | None) -> float | None:
    """Commission totale d'un aller-retour, ou `None` si une jambe manque.

    `None` et non `0.0` : un fill absent n'est pas un fill gratuit. C'est exactement la
    confusion qui faisait rapporter « frais 0,00 $ » à l'audit de turnover sur un
    journal où personne n'avait jamais renseigné le champ.

    Le shortfall n'entre PAS dans cette somme — il est déjà dans les prix de fill, donc
    déjà dans le `pnl_gross` calculé sur ces prix (cf. `Fill.charge`).
    """
    if entree is None or sortie is None:
        return None
    return entree.charge + sortie.charge


def fill_produit(broker, avant: int) -> Fill | None:
    """Le fill émis par `broker` depuis l'index `avant` — `None` s'il n'a rien exécuté.

    Prendre `broker.fills[-1]` sans cette garde attribuerait le fill de l'ordre
    PRÉCÉDENT à un ordre rejeté : un coût réel imputé à une exécution qui n'a pas eu
    lieu.
    """
    fills = getattr(broker, "fills", None) or []
    return fills[-1] if len(fills) > avant else None
