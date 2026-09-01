"""Protocole IS/OOS, parcimonie des paramètres, et PORTE de déploiement par le DSR.

SPÉCIFIÉ PAR L'UTILISATEUR (01/09), module 4. Couche MINCE : le calcul du DSR vit déjà
dans `portfolio/psr`, le comptage des essais dans `research/ledger`, le contrôle des
fausses découvertes dans `research/fdr`. On ne réimplémente rien — on assemble.

LE POINT QUI DÉCIDE DE TOUT. « DSR > 95 % » est une PORTE, pas une cible. La spec le dit
elle-même : « le système n'est déployable que si le DSR final est strictement supérieur
à 95 % ». Chercher jusqu'à ce que la métrique passe reviendrait à contourner
l'instrument censé pénaliser cette recherche — le DSR n'a de sens que si le nombre
d'essais qu'il déflate est COMPTÉ, pas choisi. D'où `n_essais` lu du ledger et
jamais fourni à la main
par l'appelant optimiste.

Conséquence à assumer : un DSR de 95 % en OOS est un seuil très haut. Peu de stratégies
réelles le franchissent. Ne pas le franchir n'est pas un échec du protocole — c'est le
protocole qui fait son travail.

STATUT : SHADOW. Aucun appelant en production.
"""

from __future__ import annotations

from dataclasses import dataclass

STATUT = "SHADOW_UNCALIBRATED"
PART_IS_DEFAUT = 0.60
MAX_PARAMETRES = 3
SEUIL_DSR = 0.95


@dataclass(frozen=True)
class Partition:
    """Découpage chronologique strict. `fin_is == debut_oos` : aucun recouvrement."""

    fin_is: int
    n_is: int
    n_oos: int

    def as_dict(self) -> dict:
        return {"fin_is": self.fin_is, "n_is": self.n_is, "n_oos": self.n_oos}


def partitionner(n: int, part_is: float = PART_IS_DEFAUT) -> Partition:
    """Coupe une série de `n` points en IS puis OOS, dans l'ORDRE CHRONOLOGIQUE.

    Chronologique et non aléatoire : un découpage tiré au hasard mettrait des points
    postérieurs dans l'échantillon d'apprentissage, ce qui est un look-ahead pur — et
    la validation « à l'aveugle » ne validerait plus rien.
    """
    if n < 10:
        raise ValueError(f"{n} points : trop court pour partitionner honnêtement")
    if not 0.1 <= part_is <= 0.9:
        raise ValueError("part_is doit rester dans [0,1 ; 0,9]")
    fin = int(round(n * part_is))
    fin = max(1, min(n - 1, fin))
    return Partition(fin_is=fin, n_is=fin, n_oos=n - fin)


def parcimonie(parametres: dict, maximum: int = MAX_PARAMETRES) -> dict:
    """Règle 4.2 : au-delà de `maximum` paramètres OPTIMISABLES, on rejette.

    Ne comptent que les paramètres réellement ajustés pendant la recherche. Les
    constantes structurelles (une fenêtre imposée par la définition d'une MM200, par
    exemple) ne sont pas des degrés de liberté : les compter gonflerait
    artificiellement le rejet, et pousserait à cacher des paramètres plutôt qu'à en
    retirer.
    """
    n = len(parametres)
    return {"statut": STATUT, "n_parametres": n, "maximum": maximum,
            "accepte": n <= maximum,
            "parametres": sorted(parametres),
            "motif": ("" if n <= maximum else
                      f"{n} paramètres optimisables > {maximum} : chaque degré de "
                      "liberté supplémentaire achète de la performance en échantillon "
                      "sans en promettre hors échantillon")}


def porte_de_deploiement(sharpe_oos: float, n_obs_oos: int, n_essais: int,
                         *, ecart_type_sharpe: float | None = None,
                         skew: float = 0.0, kurtosis: float = 3.0,
                         seuil: float = SEUIL_DSR) -> dict:
    """Verdict de déployabilité. `sharpe_oos` est PAR PÉRIODE, comme le veut `psr`.

    Par période et non annualisé : mélanger les deux plaçait le seuil du DSR à un Sharpe
    annualisé de ~27, donc jamais franchissable — l'audit du 20/08 du dépôt documente
    précisément ce piège dans `research/ledger.deflation_params`.
    """
    from packages.portfolio.psr import deflated_sharpe_ratio
    if n_obs_oos < 2 or n_essais < 1:
        return {"statut": STATUT, "deployable": False, "dsr": None,
                "motif": "échantillon hors-échantillon ou nombre d'essais insuffisant"}
    dsr = deflated_sharpe_ratio(sharpe_oos, n_obs_oos, n_essais,
                                skew=skew, kurt=kurtosis, sr_std=ecart_type_sharpe)
    ok = dsr > seuil
    return {
        "statut": STATUT, "deployable": bool(ok), "dsr": round(float(dsr), 4),
        "seuil": seuil, "n_essais": n_essais, "n_obs_oos": n_obs_oos,
        "motif": ("" if ok else
                  f"DSR {dsr:.3f} ≤ {seuil} après déflation de {n_essais} essai(s) : "
                  "le résultat hors échantillon ne se distingue pas du meilleur d'une "
                  "recherche de cette taille"),
    }


def essais_du_ledger(chemin=None) -> int:
    """Nombre d'essais RÉELLEMENT enregistrés — jamais un chiffre fourni à la main.

    C'est la garantie qui empêche de contourner le DSR : un appelant qui déclarerait
    « un seul essai » obtiendrait un seuil bas et une porte grande ouverte.
    """
    from packages.research.ledger import trial_count
    return int(trial_count(chemin) if chemin else trial_count())
