"""Les chiffres du site bouclent-ils sur le capital réel ? On pose l'identité.

LA QUESTION POSÉE (18/09) : « la somme des gains/pertes de l'historique des positions,
plus le gain/perte en cours, doit bien faire le capital réel, non ? »

NON, ET C'EST UNE QUESTION DE DIMENSION, pas de justesse des chiffres. Un réalisé et un
latent sont des VARIATIONS ; le capital réel est un NIVEAU. Leur somme vaut la variation
du compte, pas le compte. L'identité complète d'une période s'écrit :

    capital(fin) = capital(début) + réalisé + latent(fin) − latent(DÉBUT) + flux − frais

Le terme qui manque presque toujours à l'intuition est `latent(début)` : le gain ou la
perte NON RÉALISÉ que portaient déjà les positions au premier point de la courbe. Il
n'est pas mesurable a posteriori sans prix de revient antérieurs à la courbe — c'est
donc lui, pour l'essentiel, que ce module publie comme RÉSIDU.

CE QUE CE MODULE NE FAIT PAS, ET C'EST LE POINT. Il ne bouche pas l'écart. Un
rapprochement qui tombe juste parce qu'on y a mis un terme d'ajustement ne prouve rien
et masque ce qu'il fallait voir. Le résidu est calculé, nommé, rapporté au capital, et
laissé tel quel. S'il enfle, c'est un signal ; s'il tient, c'est une mesure.

DEUX PÉRIMÈTRES, ET LES CONFONDRE FAUSSE TOUT. Le panneau « Historique des positions »
montre les trades du ROBOT (cf. `packages.execution.perimetre_journal`) ; le compte,
lui, subit AUSSI l'import historique. L'identité se pose donc sur le réalisé TOTAL,
et le sous-ensemble affiché est rendu à côté pour que l'écart soit lisible.
"""

from __future__ import annotations

# En deçà, l'écart est du frottement (frais hors P&L, arrondis de fills). Au-delà, il
# porte un terme structurel qu'il faut nommer — et c'est le cas aujourd'hui.
TOLERANCE_ABS = 50.0
TOLERANCE_REL = 0.005          # 0,5 % du capital


def _bornes(pts: list[dict]) -> dict | None:
    """(premier, dernier) d'une courbe d'equity. Moins de 2 points ⇒ rien à réconcilier.

    Un seul point ne définit pas une variation : le dire vaut mieux que de renvoyer
    zéro, qui se lirait comme « le compte n'a pas bougé ».
    """
    propres = [p for p in (pts or []) if p.get("v") is not None]
    if len(propres) < 2:
        return None
    return {"debut": propres[0].get("t"), "fin": propres[-1].get("t"),
            "initial": float(propres[0]["v"]), "final": float(propres[-1]["v"]),
            "points": len(propres)}


def capital(courbes: dict[str, list[dict]]) -> dict:
    """Capital initial et final, SOMMÉS sur les comptes, avec la fenêtre de chacun.

    Les fenêtres peuvent différer (une poche ouverte plus tard, ou arrêtée). On somme
    quand même — c'est bien le capital total que la page affiche — mais on publie chaque
    fenêtre, parce qu'additionner deux périodes différentes est exactement le genre de
    détail qui rend un rapprochement faux sans que rien ne le dise.
    """
    if isinstance(courbes, list):
        # Une courbe nue au lieu d'un dict de courbes : l'erreur est naturelle, et un
        # `AttributeError` sur `.items()` ne dit pas quoi corriger.
        raise TypeError("courbes attend {compte: points}, pas une liste de points")
    fenetres, initial, final = [], 0.0, 0.0
    for compte, pts in sorted((courbes or {}).items()):
        b = _bornes(pts)
        if not b:
            continue
        fenetres.append({"compte": compte, **b})
        initial += b["initial"]
        final += b["final"]
    return {"fenetres": fenetres, "initial": round(initial, 2),
            "final": round(final, 2),
            "memes_fenetres": len({(f["debut"], f["fin"]) for f in fenetres}) <= 1}


def _montant(x: float) -> str:
    """Espace fine sur les MILLIERS, et sur eux seuls.

    Un `replace(",", " ")` appliqué à la phrase entière effacerait aussi ses virgules de
    ponctuation — le dépôt a déjà payé ce défaut une fois (`annotation_churn`). On
    formate donc le NOMBRE, jamais le texte qui l'entoure.
    """
    return f"{x:+,.2f}".replace(",", " ")


def _phrase(residu: float, boucle: bool, capital_final: float) -> str:
    if boucle:
        return ("Le compte et le registre disent la même chose, à la tolérance de "
                "frottement près.")
    part = abs(residu) / capital_final if capital_final else 0.0
    return (
        f"Il reste {_montant(residu)} $ ({part:.1%} du capital) que le registre "
        "n'explique pas. L'identité omet `latent(début)` — le gain ou la perte non "
        "réalisé que portaient DÉJÀ les positions au premier point de la courbe — et "
        "les frais hors P&L. C'est là qu'il faut le chercher ; il n'est pas comblé ici."
    )


def reconcilier(courbes: dict[str, list[dict]], realise: float, latent: float,
                *, realise_affiche: float | None = None, flux: float = 0.0) -> dict:
    """L'identité, remplie terme à terme. `disponible=False` si la courbe manque.

    `realise` est le réalisé TOTAL subi par le compte (import compris) ;
    `realise_affiche` le sous-ensemble du panneau, rendu pour comparaison.
    `latent` est celui des positions RÉELLES lues chez le courtier, jamais estimé.
    """
    cap = capital(courbes)
    if not cap["fenetres"]:
        return {"disponible": False,
                "motif": "aucune courbe d'equity enregistrée — rien à réconcilier",
                **cap}
    attendu = cap["initial"] + realise + latent + flux
    residu = cap["final"] - attendu
    seuil = max(TOLERANCE_ABS, TOLERANCE_REL * abs(cap["final"]))
    boucle = abs(residu) <= seuil
    return {
        "disponible": True, **cap,
        "capital_initial": cap["initial"], "capital_final": cap["final"],
        "realise": round(realise, 2), "latent": round(latent, 2),
        "realise_affiche": (None if realise_affiche is None
                            else round(realise_affiche, 2)),
        "hors_panneau": (None if realise_affiche is None
                         else round(realise - realise_affiche, 2)),
        "flux": round(flux, 2), "attendu": round(attendu, 2),
        "residu": round(residu, 2),
        "residu_part": round(residu / cap["final"], 4) if cap["final"] else None,
        "seuil": round(seuil, 2), "boucle": boucle,
        "explication": _phrase(residu, boucle, cap["final"]),
    }
