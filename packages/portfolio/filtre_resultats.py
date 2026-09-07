"""Écarter les candidats dont les résultats tombent trop tôt — risque BINAIRE non diversifiable.

POURQUOI CE FILTRE N'EST PAS UNE OPTION DE CONFORT. Une covariance historique mesure le
risque ORDINAIRE : celui qui se diversifie, se répartit, s'annule partiellement entre
lignes. L'annonce de résultats ne relève pas de ce régime. C'est un événement daté, connu
à l'avance, dont l'issue est binaire et dont l'amplitude (des gaps de 20 à 30 %) n'a aucune
raison de compenser celle d'un autre titre. Un min-variance ne le voit pas et recommandera
sans hésiter d'entrer trois jours avant une publication : il vend alors une sécurité que
son modèle n'a jamais mesurée.

`packages/strategies/earnings_blackout` portait déjà l'intention dans sa docstring — « à
utiliser comme filtre d'entrée » — sans que rien ne l'appelle. C'est ce câblage.

DATE INCONNUE ≠ PAS DE RÉSULTATS. Un symbole dont la date est introuvable (hors-ligne,
commodité, crypto, ETF) est CONSERVÉ mais publié à part : l'exclure viderait la sélection,
le garder en silence laisserait croire que le filtre l'a couvert. Il ne l'a pas couvert.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as _Timeout
from datetime import UTC, datetime

FENETRE_DEFAUT = 7          # jours : même valeur que l'alerte sur positions détenues
BUDGET_SECONDES = 20.0      # au-delà, on rend la main : un écran ne doit pas attendre le réseau


def _jours(symbole: str, maintenant: datetime | None) -> tuple[str, int | None]:
    from packages.strategies.earnings_blackout import days_to_next_earnings
    try:
        return symbole, days_to_next_earnings(symbole, maintenant)
    except Exception:  # noqa: BLE001 — réseau, parsing : l'inconnu se dit, il ne se devine pas
        return symbole, None


def dates_resultats(symboles: list[str], maintenant: datetime | None = None,
                    budget: float = BUDGET_SECONDES) -> dict[str, int | None]:
    """Jours avant les prochains résultats, par symbole. None = inconnu, jamais « aucun ».

    Les appels sont parallélisés et bornés par un budget de temps : la mesure est utile,
    mais pas au point de faire attendre une page. Ce qui n'a pas répondu reste `None` —
    inconnu, donc signalé, jamais transformé en « pas de résultats ».
    """
    maintenant = maintenant or datetime.now(UTC)
    sortie: dict[str, int | None] = dict.fromkeys(symboles)
    if not symboles:
        return sortie
    with ThreadPoolExecutor(max_workers=min(8, len(symboles))) as pool:
        futurs = [pool.submit(_jours, s, maintenant) for s in symboles]
        for futur in futurs:
            try:
                symbole, jours = futur.result(timeout=budget)
                sortie[symbole] = jours
            except (_Timeout, Exception):  # noqa: BLE001
                continue
    return sortie


def ecarter(symboles: list[str], fenetre: int = FENETRE_DEFAUT,
            maintenant: datetime | None = None,
            dates: dict[str, int | None] | None = None) -> tuple[list[str], list[dict], list[str]]:
    """(retenus, écartés avec le nombre de jours, symboles à date inconnue).

    `dates` permet d'injecter une mesure déjà faite — les tests s'en servent pour ne
    dépendre d'aucun réseau, et un appelant peut réutiliser un relevé récent.
    """
    if fenetre <= 0:
        return list(symboles), [], []
    connues = dates if dates is not None else dates_resultats(symboles, maintenant)
    retenus, ecartes, inconnus = [], [], []
    for symbole in symboles:
        jours = connues.get(symbole)
        if jours is None:
            inconnus.append(symbole)
            retenus.append(symbole)
        elif 0 <= jours <= fenetre:
            ecartes.append({"symbol": symbole, "days": jours,
                            "reason": f"résultats dans {jours} j — risque binaire non diversifiable"})
        else:
            retenus.append(symbole)
    ecartes.sort(key=lambda ligne: ligne["days"])
    return retenus, ecartes, inconnus
