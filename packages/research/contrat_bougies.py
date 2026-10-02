"""Un essai, figé avant d'avoir vu son résultat. Aucun ordre n'en sort.

Question : avec les 20 dernières bougies quotidiennes, leur volume, la dernière
surprise de résultats déjà publiée et le dernier fondamental déjà publié, les
10 bougies suivantes touchent-elles +4 % avant −1,25 % ?

0,04 / 0,0125 = 3,2, donc le rapport gain/risque est strictement au-dessus de 3.
Les deux informations sont ici, pas dans deux essais. Un trou (pas de publication
antérieure) est un drapeau « inconnu », jamais un zéro qui se lirait « neutre ».
"""

from __future__ import annotations

import numpy as np

GAIN = 0.04
STOP = 0.0125
HORIZON = 10
FENETRE = 20
COUT_ALLER_RETOUR = 0.001

NOMS = (
    "ret_1", "ret_5", "ret_10", "ret_fenetre",
    "volume_vs_moyenne", "amplitude", "position_dans_la_fenetre",
    "surprise_resultats", "surprise_connue",
    "fondamental", "fondamental_connu",
)


def rapport() -> float:
    """Gain divisé par le risque. Figé, pas optimisé."""
    return GAIN / STOP


def seuil_brut(cout: float = COUT_ALLER_RETOUR) -> float:
    """Fréquence à partir de laquelle le pari gagne encore, frais compris.

    Un gain paie `GAIN − coût`, un stop coûte `STOP + coût`. En dessous de ce
    seuil, même une probabilité juste perd de l'argent.
    """
    return (STOP + cout) / (GAIN + STOP)


def decision(proba: float | None, calibre: bool) -> str:
    """`candidat` n'est pas un ordre. Tout le reste est une abstention."""
    if not calibre or proba is None:
        return "abstention"
    if not np.isfinite(proba) or proba <= seuil_brut():
        return "abstention"
    return "candidat"


def derniere_connue(publications: list[tuple], decision) -> tuple[float, float]:
    """(valeur, 1) si une publication a eu lieu AVANT la décision, sinon (0, 0).

    Le jour même est exclu : une publication après la clôture n'est pas connue
    quand on décide sur cette clôture.
    """
    connue = None
    for date, valeur in publications:
        if valeur is None or not (date < decision):
            continue
        if connue is None or date >= connue[0]:
            connue = (date, float(valeur))
    if connue is None:
        return 0.0, 0.0
    return connue[1], 1.0


def issue(high, low, close, i: int) -> int | None:
    """1 si +4 % est touché avant le stop, 0 si le stop ou le temps gagne.

    None si l'avenir n'est pas entier, ou si la même bougie contient les deux
    barrières : l'ordre intradable est inconnu, l'échantillon est écarté.
    """
    if i < 0 or i + HORIZON >= len(close):
        return None
    entree = float(close[i])
    if entree <= 0:
        return None
    haut, bas = entree * (1.0 + GAIN), entree * (1.0 - STOP)
    for j in range(i + 1, i + HORIZON + 1):
        gagne = float(high[j]) > haut
        perdu = float(low[j]) <= bas
        if gagne and perdu:
            return None
        if gagne:
            return 1
        if perdu:
            return 0
    return 0


def _rendement(close, i: int, k: int) -> float:
    depart = float(close[i - k])
    return float(close[i]) / depart - 1.0 if depart > 0 else 0.0


def ligne_prix(close, high, low, volume, i: int) -> list[float] | None:
    """Sept nombres lus uniquement sur les bougies déjà closes, décision incluse."""
    if i < FENETRE:
        return None
    if float(close[i]) <= 0:
        return None
    vols = np.asarray(volume[i - FENETRE + 1:i + 1], float)
    moy = float(vols.mean()) if vols.size else 0.0
    volume_rel = float(vols[-1]) / moy - 1.0 if moy > 0 else 0.0
    fenetre = np.asarray(close[i - FENETRE + 1:i + 1], float)
    lo, hi = float(fenetre.min()), float(fenetre.max())
    position = (float(close[i]) - lo) / (hi - lo) if hi > lo else 0.5
    amplitude = (float(high[i]) - float(low[i])) / float(close[i])
    return [
        _rendement(close, i, 1), _rendement(close, i, 5),
        _rendement(close, i, 10), _rendement(close, i, FENETRE),
        volume_rel, amplitude, position,
    ]


def ligne(close, high, low, volume, i: int, decision_date,
          surprises: list[tuple], fondamentaux: list[tuple]) -> list[float] | None:
    prix = ligne_prix(close, high, low, volume, i)
    if prix is None:
        return None
    surprise, surprise_ok = derniere_connue(surprises, decision_date)
    fond, fond_ok = derniere_connue(fondamentaux, decision_date)
    return [*prix, surprise, surprise_ok, fond, fond_ok]


def construire(close, high, low, volume, dates,
               surprises: list[tuple] | None = None,
               fondamentaux: list[tuple] | None = None):
    """Matrice (lignes, 11) et étiquettes. Les lignes sans avenir entier sortent."""
    surprises = list(surprises or [])
    fondamentaux = list(fondamentaux or [])
    xs, ys = [], []
    for i, date in enumerate(dates):
        y = issue(high, low, close, i)
        x = None if y is None else ligne(
            close, high, low, volume, i, date, surprises, fondamentaux)
        if x is None:
            continue
        xs.append(x)
        ys.append(y)
    if not xs:
        return np.empty((0, len(NOMS))), np.empty(0, dtype=int)
    return np.asarray(xs, float), np.asarray(ys, int)
