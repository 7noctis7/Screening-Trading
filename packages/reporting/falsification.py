"""« Qu'est-ce qui invaliderait cette thèse ? » — des critères OBSERVABLES.

CE QUE CE MODULE N'EST PAS. Ce n'est pas un contre-argumentaire. Un texte qui
plaide le camp adverse produit deux argumentaires convaincants et aucune
décision : on l'a vu sur un rapport où le haussier et le baissier affichaient
tous deux ~50 % de confiance sur le même titre, avec des cibles allant de 50 $ à
140 $. Ce n'est pas de l'information, c'est de la mise en scène du doute.

CE QU'IL EST. Une liste de FAITS MESURABLES qui, s'ils se produisent, ferment la
position. Chaque critère porte sa valeur actuelle, son seuil et la distance qui
les sépare. On écrit la sortie AVANT l'entrée, et on peut vérifier chaque jour si
elle est atteinte — ce qu'aucun paragraphe d'opinion ne permet.

TROIS RÈGLES.

1. UN CRITÈRE NON CALCULABLE N'EST PAS PUBLIÉ. Pas de « si les fondamentaux se
   dégradent » : soit on a la donnée et le seuil est chiffré, soit le critère
   n'existe pas. Le mandat données-réelles, appliqué à la sortie.
2. UN CRITÈRE DÉJÀ FRANCHI INVALIDE LA THÈSE, ET LE DIT. Sans cette règle la
   section devient décorative : de beaux critères publiés sous une recommandation
   qu'ils contredisent déjà. C'est le défaut exact du rapport cité — un
   gestionnaire de risque qui REFUSE, et un en-tête « BULLISH » quand même.
3. LE SENS DÉPEND DE LA RECOMMANDATION. Un critère de sortie pour un achat n'est
   pas celui d'une vente. Sur une position neutre, la section se tait plutôt que
   d'inventer une thèse à invalider.
"""

from __future__ import annotations

ACHAT = ("acheter", "achat", "buy", "renforcer")
VENTE = ("vendre", "vente", "sell", "alleger", "alléger")

_UNCALIBRATED = ("UNCALIBRATED : aucune donnée ne permet de chiffrer un critère de "
                 "sortie. Une thèse qu'on ne peut pas invalider ne se prend pas.")


def _critere(libelle: str, actuel: float | None, seuil: float | None, sous: bool,
             consequence: str) -> dict | None:
    """Un critère chiffré, ou None s'il manque une valeur (règle 1)."""
    if actuel is None or seuil is None:
        return None
    a, s = float(actuel), float(seuil)
    # Distance RELATIVE : « à 8 % du stop » se compare d'un titre à l'autre,
    # « à 4,12 $ du stop » ne se compare à rien.
    ecart = (a - s) / abs(s) if s else None
    return {"critere": libelle, "actuel": round(a, 4), "seuil": round(s, 4),
            "sens": "sous" if sous else "au-dessus",
            "declenche": bool(a < s if sous else a > s),
            "distance_relative": round(ecart, 4) if ecart is not None else None,
            "consequence": consequence}


def _pour_un_achat(cours, stop, ma200, roce, wacc, croissance_ca) -> list:
    return [
        _critere("clôture sous le stop (≈2σ hebdo)", cours, stop, True,
                 "sortie : le scénario de prix est démenti"),
        _critere("clôture sous la moyenne 200 jours", cours, ma200, True,
                 "la tendance de fond n'est plus porteuse"),
        _critere("ROCE retombé sous le WACC", roce, wacc, True,
                 "la société détruit de la valeur : la thèse de qualité tombe"),
        _critere("croissance du chiffre d'affaires négative", croissance_ca, 0.0,
                 True, "la thèse de croissance tombe"),
    ]


def _pour_une_vente(cours, stop, ma200) -> list:
    return [
        _critere("clôture au-dessus du stop (≈2σ hebdo)", cours, stop, False,
                 "sortie : le scénario de baisse est démenti"),
        _critere("clôture au-dessus de la moyenne 200 jours", cours, ma200, False,
                 "la tendance de fond redevient porteuse"),
    ]


def falsifieurs(*, reco: str, cours: float | None = None,
                stop: float | None = None, ma200: float | None = None,
                roce: float | None = None, wacc: float | None = None,
                croissance_ca: float | None = None,
                drawdown_courant: float | None = None,
                max_drawdown: float | None = None) -> dict:
    """Ce qui fermerait la position, chiffré. {applicable, invalidee, criteres}."""
    r = (reco or "").strip().lower()
    long = any(k in r for k in ACHAT)
    court = any(k in r for k in VENTE)
    if not (long or court):
        return {"applicable": False, "invalidee": False, "criteres": [],
                "motif": f"recommandation « {reco or '—'} » : aucune position "
                         "à invalider"}

    bruts = (_pour_un_achat(cours, stop, ma200, roce, wacc, croissance_ca)
             if long else _pour_une_vente(cours, stop, ma200))
    # Le drawdown vaut pour les DEUX sens : dépasser le pire recul observé signifie
    # que la position sort du domaine où le risque a été MESURÉ, quel que soit son
    # sens. C'est le seul critère qui ne dépend pas de la thèse.
    bruts.append(_critere("recul dépassant le pire drawdown mesuré",
                          drawdown_courant, max_drawdown, True,
                          "le risque sort du domaine mesuré : réduire ou solder"))

    criteres = [c for c in bruts if c]
    if not criteres:
        return {"applicable": False, "invalidee": False, "criteres": [],
                "motif": _UNCALIBRATED}
    n = sum(1 for c in criteres if c["declenche"])
    return {
        "applicable": True, "criteres": criteres, "invalidee": n > 0,
        "n_declenches": n,
        "motif": (f"{n} critère(s) DÉJÀ franchi(s) : la thèse est invalidée au "
                  "moment où elle est publiée" if n else
                  f"{len(criteres)} critère(s) de sortie chiffrés, aucun franchi"),
    }
