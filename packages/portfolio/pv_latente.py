"""Combien de plus-value latente une position a-t-elle RENDUE ? — mesurer le yo-yo.

LA QUESTION POSÉE (10/09) : « ma PV latente chute et je ne parviens pas à la
sécuriser ». Le tableau de bord montre la PV du jour ; il ne montre pas le chemin. Une
ligne montée à +900 € puis redescendue à +120 € et une ligne montée tout droit à +120 €
s'y affichent à l'identique. C'est pourtant la première qui pose problème, et rien ne
permettait de les distinguer.

CE QUE CE MODULE MESURE, sur une position ENCORE OUVERTE :
  · `pv_courante`  — la plus-value latente d'aujourd'hui ;
  · `pv_max`       — la meilleure jamais atteinte depuis l'entrée (MFE en monnaie) ;
  · `rendu`        — `pv_max − pv_courante`, ce que le marché a repris ;
  · `part_rendue`  — `rendu / pv_max`, entre 0 et 1.

CE QU'IL NE FAIT PAS. Il ne dit pas s'il FALLAIT sortir : une position qui rend 40 % de
son pic peut très bien en reprendre le double ensuite. Il chiffre un renoncement, pas
une erreur. Le module d'audit des allers-retours (`research/turnover_audit`) mesure le
même phénomène sur les lots CLOS ; celui-ci couvre les positions vivantes, que rien
n'observait — et ce sont elles que l'on regarde chuter.
"""

from __future__ import annotations

__all__ = ["agreger", "pv_rendue"]


def pv_rendue(barres: list[tuple[str, float]], entree: str, prix_entree: float,
              quantite: float, sens: str = "long") -> dict:
    """Trajectoire de la PV latente d'UNE position ouverte.

    `barres` : [(date ISO, clôture)] quelconques ; seules celles à partir de `entree`
    comptent. Une position sans barre postérieure à son entrée rend `available` faux —
    on ne devine pas un prix courant à partir d'un prix d'entrée.
    """
    apres = sorted((d, float(c)) for d, c in barres if d >= entree and c == c and c > 0)
    if not apres or quantite == 0 or prix_entree <= 0:
        return {"available": False, "motif": "aucune barre après l'entrée"}
    signe = -1.0 if sens == "short" else 1.0
    pvs = [(d, signe * (c - prix_entree) * quantite) for d, c in apres]
    date_max, pv_max = max(pvs, key=lambda x: x[1])
    date_courante, pv_courante = pvs[-1]
    rendu = max(0.0, pv_max - pv_courante)
    return {
        "available": True,
        "n_barres": len(pvs),
        "date_pic": date_max, "pv_max": pv_max,
        "date_courante": date_courante, "pv_courante": pv_courante,
        "rendu": rendu,
        # Une PV maximale négative ou nulle n'a rien à rendre : la position n'est jamais
        # passée en gain. Diviser par elle produirait une « part rendue » de signe
        # arbitraire, c'est-à-dire un chiffre qui a l'air d'en être un.
        "part_rendue": (rendu / pv_max) if pv_max > 0 else 0.0,
        "jamais_en_gain": pv_max <= 0,
    }


def agreger(lignes: list[dict]) -> dict:
    """Total du portefeuille : PV du pic, PV du jour, et ce qui sépare les deux.

    Les pics de deux lignes ne sont PAS simultanés : leur somme est un maximum
    théorique que le portefeuille n'a jamais affiché. On l'appelle donc « somme des
    pics » et pas « pic du portefeuille » — nommer juste évite de croire qu'on aurait
    pu encaisser ce total d'un seul geste.
    """
    utiles = [x for x in lignes if x.get("available")]
    somme_pics = sum(x["pv_max"] for x in utiles)
    courante = sum(x["pv_courante"] for x in utiles)
    part = ((somme_pics - courante) / somme_pics) if somme_pics > 0 else 0.0
    return {
        "n_positions": len(utiles),
        "somme_des_pics": somme_pics,
        "pv_courante": courante,
        "rendu": sum(x["rendu"] for x in utiles),
        "part_rendue": part,
        "n_jamais_en_gain": sum(1 for x in utiles if x["jamais_en_gain"]),
    }
