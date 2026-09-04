"""Identifie les lots « ouverts » qui sont en réalité des VENTES écrites à l'endroit
des entrées.

CE QUE LA MESURE A DIT (03/09, compte réel). La partie FERMÉE du journal égale la
quantité achetée au dix-millième — 79 symboles sur 87 exactement, les 8 autres étant
ceux dont une position est encore ouverte. L'appariement des sorties est donc juste.
Tout l'excédent tient dans des lots OUVERTS, et 33 des 52 lots ouverts portent le
symbole, la quantité et le prix EXACTS d'une vente exécutée chez le courtier :

    ICLN 301,600106 @ 20,8300 le 23/06 — jour et prix de la vente qui a soldé le titre
    NWL  155,375433 @  5,7800 le 25/06 — quantité au millionième de la sortie « -R1 »

Un tel enregistrement ne décrit pas une entrée. C'est ce qui produisait le rapport
2,0000 × entre journal et quantité achetée : le registre portait `acheté + vendu`.

POURQUOI UN RETRAIT ET NON UNE ÉCRITURE DE CORRECTION. Le dépôt corrige, il ne réécrit
pas — c'est la règle, et elle vaut pour une VALEUR fausse. Ici la valeur n'est pas
fausse : l'opération n'a pas eu lieu dans ce sens. On ne corrige pas une position
imaginaire, on la retire, et on archive la ligne retirée avec la preuve qui l'a
désignée. Le fermer à son prix d'entrée serait pire : cela publierait un aller-retour
à 0,00 $ qui n'a jamais existé, et gonflerait le compte de trades.

LE CRITÈRE EST STRICT, ET C'EST VOULU. Symbole canonique, quantité et prix identiques
à un fill de VENTE unique. Une vente exécutée en plusieurs fills n'a pas de fill de
même quantité et ne sera PAS appariée : le lot reste ouvert et reste signalé. Le compte
est un PLANCHER — il sous-estime, il ne peut pas surestimer. C'est la seule direction
d'erreur acceptable pour une mesure qui décide d'un retrait.
"""

from __future__ import annotations

from packages.research.biais_fermeture import symbole_canonique


def signature(sym: str, qty: float, prix: float) -> tuple:
    """Signature d'un fill, arrondie à ce que les deux sources savent porter.

    Quatre décimales sur la quantité et le prix : au-delà, le courtier et le journal
    divergent par des arrondis de sérialisation et rien ne s'apparierait jamais."""
    return (symbole_canonique(sym), round(float(qty or 0), 4),
            round(float(prix or 0), 4))


def ventes_du_courtier(ordres: list[dict]) -> dict[tuple, dict]:
    """Signatures des fills de VENTE exécutés, vers le fill qui les porte."""
    out: dict[tuple, dict] = {}
    for o in ordres or []:
        if o.get("side") != "sell":
            continue
        q, px = float(o.get("qty") or 0), float(o.get("price") or 0)
        if q <= 0 or px <= 0:
            continue
        out.setdefault(signature(o.get("symbol", ""), q, px), o)
    return out


def lots_a_annuler(lots_ouverts: list, ventes: dict[tuple, dict]) -> list[dict]:
    """Lots ouverts dont la signature est celle d'une vente exécutée. Aucune écriture.

    Renvoie, pour chaque lot, l'enregistrement ET le fill qui le désigne : la preuve
    voyage avec la décision, sinon l'archive ne permet pas de la rejuger."""
    a_annuler = []
    for t in lots_ouverts:
        if t.exit_ts is not None:
            continue
        cle = signature(t.instrument, t.qty, t.entry_price)
        fill = ventes.get(cle)
        if fill is None:
            continue
        a_annuler.append({"lot": t, "fill": fill, "signature": cle})
    return a_annuler


def archive(entree: dict) -> dict:
    """Ligne d'archive JSON : ce qui est retiré, et ce qui a justifié le retrait."""
    t, f = entree["lot"], entree["fill"]
    return {
        "id": t.id, "instrument": t.instrument, "venue": t.venue,
        "qty": float(t.qty or 0), "entry_price": float(t.entry_price or 0),
        "entry_ts": str(t.entry_ts), "entry_reason": t.entry_reason,
        "preuve_vente": {"symbol": f.get("symbol"), "qty": f.get("qty"),
                         "price": f.get("price"), "date": f.get("date"),
                         "id": f.get("id")},
    }
