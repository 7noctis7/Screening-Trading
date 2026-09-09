"""Combien de plus-value latente une position a-t-elle RENDUE ? — mesurer le yo-yo.

LA QUESTION POSÉE (10/09) : « ma PV latente chute et je ne parviens pas à la
sécuriser ». Le tableau de bord montre la PV du jour ; il ne montre pas le chemin. Une
ligne montée à +900 € puis redescendue à +120 € et une ligne montée tout droit à +120 €
s'y affichent à l'identique. C'est pourtant la première qui pose problème, et rien ne
permettait de les distinguer.

CE QUE CE MODULE MESURE, sur une position ENCORE OUVERTE :
  · `pv_courante`  — la plus-value latente d'aujourd'hui ;
  · `pv_max`       — la meilleure jamais atteinte depuis l'entrée (MFE en monnaie) ;
  · `rendu_du_gain`     — la part du PIC DE GAIN reprise par le marché, bornée par ce
                          pic : c'est le yo-yo au sens strict ;
  · `perte_sous_entree` — ce qui manque SOUS le prix d'entrée. Autre problème, autre
                          geste : un stop, pas un objectif de gain ;
  · `part_rendue`       — `rendu_du_gain / pic`, dans [0, 1].

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
    # DEUX CHOSES QUI NE SE MÉLANGENT PAS, et que la première version additionnait.
    #
    # `pv_max − pv_courante` confond « j'ai rendu un gain » et « je suis passé sous mon
    # prix d'entrée ». Sur données réelles (10/09), une ligne montée à +17 $ puis tombée
    # à −1 329 $ affichait « 7 975 % rendus » : le rapport n'a plus aucun sens, et il
    # désigne le mauvais coupable. Seuls 17 $ ont jamais été un gain à sécuriser ;
    # les 1 329 $ restants sont une perte, qu'aucune prise de bénéfice n'aurait évitée —
    # cela demande un stop, pas un objectif. Les deux appellent des gestes différents,
    # donc deux chiffres différents.
    gain_max = max(0.0, pv_max)
    rendu_du_gain = min(gain_max, max(0.0, pv_max - pv_courante))
    return {
        "available": True,
        "n_barres": len(pvs),
        "date_pic": date_max, "pv_max": pv_max,
        "date_courante": date_courante, "pv_courante": pv_courante,
        "rendu_du_gain": rendu_du_gain,
        "perte_sous_entree": max(0.0, -pv_courante),
        # Bornée à [0, 1] par construction : c'est une PART du gain atteint, pas un
        # rapport entre deux quantités de natures différentes.
        "part_rendue": (rendu_du_gain / gain_max) if gain_max > 0 else 0.0,
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
    # On ne somme que les pics POSITIFS. Additionner le « pic » d'une ligne qui n'a
    # jamais été en gain — donc un nombre négatif — donnait un total de −1 916 $ sur le
    # portefeuille réel : un « sommet » sous zéro, dont on déduisait ensuite une part
    # rendue de 0 %. Le chiffre était faux ET rassurant, la pire combinaison.
    gains_max = sum(max(0.0, x["pv_max"]) for x in utiles)
    rendu = sum(x["rendu_du_gain"] for x in utiles)
    return {
        "n_positions": len(utiles),
        "somme_des_gains_max": gains_max,
        "pv_courante": sum(x["pv_courante"] for x in utiles),
        "rendu_du_gain": rendu,
        "perte_sous_entree": sum(x["perte_sous_entree"] for x in utiles),
        "part_rendue": (rendu / gains_max) if gains_max > 0 else 0.0,
        "n_jamais_en_gain": sum(1 for x in utiles if x["jamais_en_gain"]),
    }
