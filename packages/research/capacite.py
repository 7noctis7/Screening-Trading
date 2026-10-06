"""Encours où l'espérance nette d'un aller-retour devient NULLE (capacité).

Un coût en pourcentage fixe ne dépend pas de la taille : il ne dit jamais quand la
stratégie cesse de payer. L'impact, si — en racine carrée de la participation
(`packages.execution.impact`, modèle Almgren-Chriss / Torre) :

    impact = Y · σ_jour · √(q / ADV)        (par côté, en fraction)

On rejoue les MÊMES allers-retours avec des quantités multipliées par k (le livre
k fois plus gros), et l'on cherche k* tel que l'espérance nette pondérée s'annule.
Encours de capacité = capital du rejeu × k*.

PARAMÈTRES. ADV et σ sont lus sur les 20 séances qui PRÉCÈDENT l'exécution (rien du
jour même). Y n'est pas calibré sur le TCA réel : la capacité est publiée pour une
PLAGE de Y (0,5 et 1,0, bornes du consensus cité dans `impact.py`), jamais pour une
seule valeur présentée comme mesurée. Exécution supposée étalée sur la séance entière :
hypothèse favorable, la capacité réelle est plus basse.
"""

from __future__ import annotations

from bisect import bisect_left

import numpy as np

FENETRE = 20
Y_PLAGE = (0.5, 1.0)


class Marche:
    """ADV (titres) et σ quotidienne PRÉCÉDANT une date, depuis les barres."""

    def __init__(self, data: dict) -> None:
        from packages.backtest.panel import _jour
        self._s = {}
        for s, barres in data.items():
            j = [_jour(b) for b in barres]
            c = np.asarray([float(b.close or 0) for b in barres])
            v = np.asarray([float(getattr(b, "volume", 0) or 0) for b in barres])
            self._s[s] = (j, c, v)

    def adv_sigma(self, sym: str, jour: str) -> tuple[float, float] | None:
        if sym not in self._s:
            return None
        j, c, v = self._s[sym]
        i = bisect_left(j, jour)                       # séances STRICTEMENT avant
        if i < FENETRE + 1:
            return None
        cc, vv = c[i - FENETRE - 1:i], v[i - FENETRE:i]
        if (cc <= 0).any() or vv.mean() <= 0:
            return None
        r = cc[1:] / cc[:-1] - 1.0
        return float(vv.mean()), float(r.std(ddof=1))


def impact(q: float, adv: float, sigma: float, y: float) -> float:
    """Impact d'un côté, en fraction du notionnel (séance entière)."""
    from packages.execution.impact import square_root_impact_bps
    return square_root_impact_bps(q, adv, sigma * 1e4, y=y) / 1e4


def _param(marche: Marche, ar: dict) -> tuple | None:
    a = marche.adv_sigma(ar["sym"], ar["achat"])
    v = marche.adv_sigma(ar["sym"], ar["vente"])
    return (a, v) if a and v else None


def esperance_a_l_echelle(ars: list[dict], params: list, k: float, y: float) -> float:
    """Espérance nette pondérée quand chaque quantité est multipliée par k."""
    from packages.research.aller_retour import rendement_net
    num = den = 0.0
    for ar, p in zip(ars, params, strict=True):
        (adv_a, sg_a), (adv_v, sg_v) = p
        q = ar["q"] * k
        net = rendement_net(ar, impact(q, adv_a, sg_a, y), impact(q, adv_v, sg_v, y))
        num += net * ar["notionnel"]
        den += ar["notionnel"]
    return num / den if den > 0 else float("nan")


def k_nul(ars: list[dict], params: list, y: float) -> float | None:
    """k* où l'espérance s'annule ; 0 si déjà ≤ 0 sans impact ; None au-delà de 1e6."""
    f = lambda k: esperance_a_l_echelle(ars, params, k, y)   # noqa: E731
    if f(1e-6) <= 0:
        return 0.0
    lo, hi = 1e-6, 1e6
    if f(hi) > 0:
        return None
    for _ in range(80):
        mid = (lo * hi) ** 0.5
        lo, hi = (mid, hi) if f(mid) > 0 else (lo, mid)
    return (lo * hi) ** 0.5


def capacite(ars: list[dict], data: dict, capital: float) -> dict:
    """Encours de capacité pour chaque Y de la plage (allers-retours mesurables)."""
    marche = Marche(data)
    couples = [(ar, p) for ar in ars if (p := _param(marche, ar)) is not None]
    if len(couples) < 30:
        return {"available": False, "status": "UNCALIBRATED", "n": len(couples)}
    a, p = [c[0] for c in couples], [c[1] for c in couples]
    out = {}
    for y in Y_PLAGE:
        k = k_nul(a, p, y)
        out[f"Y={y}"] = {"k": k, "encours": None if k is None else capital * k,
                         "esperance_au_capital": esperance_a_l_echelle(a, p, 1.0, y)}
    return {"available": True, "n_mesurables": len(couples), "n_total": len(ars),
            "capital_rejeu": capital, "par_y": out,
            "hypothese": "exécution étalée sur la séance ; Y non calibré"}
