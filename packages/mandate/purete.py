"""Le moteur est une FONCTION PURE du mandat — et on le vérifie mécaniquement.

Contrat. Un moteur déterministe est une fonction :

    moteur(mandat, marche, as_of) -> poids cibles

Trois propriétés, chacune vérifiable, chacune correspondant à un bug RÉEL du dépôt :

1. DÉTERMINISME — deux appels identiques rendent le même résultat.
2. INDÉPENDANCE À L'ENVIRONNEMENT — aucune variable d'environnement ne change la
   sortie. C'est le bug du 26/08 : `QUANT_LIVE_LITE=1` coupait la section
   `fundamentals`, donc `quality` était vide, donc la SÉLECTION D'UNIVERS changeait.
   Une variable d'environnement décidait quelles actions acheter, et aucune
   configuration ne le disait.
3. ÉQUIVALENCE DES CHEMINS — le même mandat au même `as_of` rend les mêmes poids,
   qu'on passe par le chemin backtest ou par le chemin production. C'est la
   propriété que les trois correctifs #347, #352 et #353 ont rétablie une par une,
   à la main, après coup. Vérifiée ici, aucun des trois n'aurait pu être écrit.

Ces fonctions RENVOIENT les anomalies au lieu de lever : on veut la liste complète,
et elles servent aussi bien en test qu'en garde-fou d'exécution.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

from packages.mandate.canonical import hacher

# Variables qui ont, ou ont eu, le pouvoir de changer une décision. Le harnais les
# bouscule volontairement : si la sortie bouge, c'est qu'une d'elles pilote le moteur.
VARIABLES_SUSPECTES = (
    "QUANT_LIVE_LITE", "QUANT_HISTORY_DAYS", "QUANT_IGNORE_SESSION",
    "QUANT_RISK_MAX_WEIGHT", "QUANT_RISK_MAX_POSITIONS", "QUANT_RISK_MAX_GROSS",
    "QUANT_CORS_ORIGINS", "TZ",
)


@contextmanager
def _environnement_bouscule(variables: tuple[str, ...]) -> Iterator[None]:
    """Force des valeurs ARBITRAIRES puis restaure exactement l'état initial."""
    avant = {v: os.environ.get(v) for v in variables}
    try:
        for i, v in enumerate(variables):
            os.environ[v] = "1" if i % 2 == 0 else "0"
        yield
    finally:
        for v, val in avant.items():
            if val is None:
                os.environ.pop(v, None)
            else:
                os.environ[v] = val


def _empreinte(sortie: Any) -> str:
    """Hash canonique d'une sortie de moteur — comparable entre appels."""
    if isinstance(sortie, dict):
        return hacher({str(k): _arrondi(v) for k, v in sortie.items()})
    return hacher(_arrondi(sortie))


def _arrondi(v: Any) -> Any:
    """Arrondit au 1e-9 : on compare des DÉCISIONS, pas le dernier bit d'un flottant.

    Sans cet arrondi, une réassociation d'opérations flottantes ferait échouer le
    test de déterminisme pour une différence qui ne change aucun ordre envoyé.
    """
    if isinstance(v, bool) or v is None or isinstance(v, str):
        return v
    if isinstance(v, (int, float)):
        return round(float(v), 9)
    if isinstance(v, dict):
        return {str(k): _arrondi(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_arrondi(x) for x in v]
    return str(v)


def verifier_determinisme(moteur: Callable[[], Any], n: int = 3) -> list[str]:
    """Appelle `moteur` n fois : toutes les sorties doivent être identiques."""
    empreintes = []
    for i in range(n):
        try:
            empreintes.append(_empreinte(moteur()))
        except Exception as e:                                  # noqa: BLE001
            return [f"appel {i + 1} a levé {type(e).__name__}: {e}"]
    distinctes = set(empreintes)
    if len(distinctes) > 1:
        return [f"moteur NON DÉTERMINISTE : {len(distinctes)} sorties distinctes "
                f"sur {n} appels identiques ({sorted(distinctes)})"]
    return []


def verifier_independance_environnement(
        moteur: Callable[[], Any],
        variables: tuple[str, ...] = VARIABLES_SUSPECTES) -> list[str]:
    """La sortie ne doit pas bouger quand on bouscule l'environnement."""
    try:
        reference = _empreinte(moteur())
    except Exception as e:                                      # noqa: BLE001
        return [f"appel de référence a levé {type(e).__name__}: {e}"]
    with _environnement_bouscule(variables):
        try:
            bouscule = _empreinte(moteur())
        except Exception as e:                                  # noqa: BLE001
            return [f"sous environnement bousculé, a levé {type(e).__name__}: {e}"]
    if bouscule != reference:
        return ["le moteur DÉPEND DE L'ENVIRONNEMENT : la sortie change quand on "
                f"modifie {list(variables)}. Une variable d'environnement ne peut pas "
                "décider d'une allocation — ce qui décide doit être DANS le mandat."]
    return []


def verifier_equivalence(
        chemin_a: Callable[[], Any], chemin_b: Callable[[], Any],
        nom_a: str = "backtest", nom_b: str = "production") -> list[str]:
    """Deux chemins censés implémenter le MÊME mandat doivent rendre la même chose."""
    try:
        ea, eb = _empreinte(chemin_a()), _empreinte(chemin_b())
    except Exception as e:                                      # noqa: BLE001
        return [f"comparaison impossible, {type(e).__name__}: {e}"]
    if ea != eb:
        return [f"DIVERGENCE {nom_a} / {nom_b} sur le même mandat : {ea[:16]} ≠ "
                f"{eb[:16]}. Les deux chemins ne calculent pas la même stratégie — "
                "c'est la classe de défaut de #347, #352 et #353."]
    return []


def auditer(moteur: Callable[[], Any]) -> list[str]:
    """Les deux vérifications applicables à un moteur seul (sans second chemin)."""
    return verifier_determinisme(moteur) + verifier_independance_environnement(moteur)
