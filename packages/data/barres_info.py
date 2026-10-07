"""Barres d'INFORMATION : volume et dollar (López de Prado, AFML ch. 2).

L'IDÉE. Une barre de temps échantillonne à heure fixe, que le marché soit calme ou
agité : les rendements ont alors une variance qui change avec l'activité
(hétéroscédasticité) et des queues épaisses. Une barre en volume (ou en dollars
échangés) se ferme quand une QUANTITÉ d'activité a été atteinte : on échantillonne plus
souvent quand il se passe davantage de choses. Sur des données tick de contrats à
terme, AFML montre des rendements plus proches de la loi normale et moins
autocorrélés. C'est une RÉDUCTION, pas une garantie d'IID : `diagnostic_iid` la
mesure sur nos données au lieu de la présumer.

LIMITES, À LIRE AVANT D'UTILISER.
- Construites à partir de barres QUOTIDIENNES, ces barres ne peuvent qu'agréger des
  jours (une barre ≥ 1 séance) : le gain de résolution exige des données intraday.
- Elles DÉSYNCHRONISENT les titres : deux actifs n'ont plus de barre au même instant.
  Le modèle de production classe des titres ENTRE EUX à une même date (coupe
  transversale) : il ne peut pas consommer ces barres sans être réécrit. Elles servent
  aux modèles série par série (un actif, crypto intraday par exemple).
- La dernière barre incomplète (seuil non atteint) est écartée, jamais complétée.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np


def _agreger(barres: list, seuil: float, mesure: Callable) -> list:
    from packages.core.models import Bar
    if seuil <= 0:
        raise ValueError("seuil > 0 requis")
    out, paquet, cumul = [], [], 0.0
    for b in barres:
        paquet.append(b)
        cumul += max(0.0, float(mesure(b)))
        if cumul >= seuil:
            out.append(Bar(instrument=b.instrument, timeframe=f"info:{seuil:g}",
                           ts=b.ts, open=paquet[0].open,
                           high=max(x.high for x in paquet),
                           low=min(x.low for x in paquet), close=b.close,
                           volume=sum(x.volume for x in paquet)))
            paquet, cumul = [], 0.0
    return out


def barres_volume(barres: list, seuil: float) -> list:
    """Une barre chaque fois que `seuil` titres (ou unités) ont été échangés."""
    return _agreger(barres, seuil, lambda b: b.volume)


def barres_dollar(barres: list, seuil: float) -> list:
    """Une barre chaque fois que `seuil` dollars ont été échangés (close × volume)."""
    return _agreger(barres, seuil, lambda b: b.close * b.volume)


def seuil_pour(barres: list, barres_par_periode: float, dollar: bool = True) -> float:
    """Seuil qui donne en moyenne `barres_par_periode` barres par barre d'entrée
    (ex. 0,2 → une barre d'information pour 5 barres de temps)."""
    m = [b.close * b.volume if dollar else b.volume for b in barres]
    moy = float(np.mean([x for x in m if x > 0])) if any(x > 0 for x in m) else 0.0
    return moy / barres_par_periode if barres_par_periode > 0 else 0.0


def diagnostic_iid(closes) -> dict:
    """Ce que les barres d'information sont censées améliorer, MESURÉ :
    autocorrélation des rendements (indépendance), autocorrélation de leurs carrés
    (variance qui se regroupe), Jarque-Bera (écart à la normale)."""
    c = np.asarray(closes, float)
    r = np.diff(np.log(c[c > 0]))
    if r.size < 30:
        return {"available": False, "n": int(r.size)}

    def ac1(x):
        x = x - x.mean()
        d = float((x * x).sum())
        return float((x[1:] * x[:-1]).sum() / d) if d > 0 else 0.0

    z = (r - r.mean()) / (r.std() or 1.0)
    s, k = float((z ** 3).mean()), float((z ** 4).mean())
    return {"available": True, "n": int(r.size), "autocorr_1": ac1(r),
            "autocorr_carres_1": ac1(r * r), "asymetrie": s, "kurtosis": k,
            "jarque_bera": float(r.size / 6 * (s * s + (k - 3) ** 2 / 4))}
