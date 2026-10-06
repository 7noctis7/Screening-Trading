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

CORRIGÉ LE 06/10 (premier passage réel). Deux défauts rendaient l'impact AVEUGLE à la
taille, donc la capacité infinie (« > 10⁶ × le capital » à Y = 0,5, mais 341 k$ à
Y = 1,0 — impossible pour une loi en racine où doubler Y divise k* par 4) :
  - un volume NaN dans la fenêtre passait le filtre (`nan <= 0` est faux) et l'ADV
    devenait NaN ; `min(1.0, q / nan)` vaut 1,0 : participation 100 %, impact = Y·σ ;
  - la participation était plafonnée à 100 % (`impact.square_root_impact_bps`, borne
    légitime pour UN ordre d'UNE séance) : au-delà, l'impact ne croissait plus avec k.
Ici, seuls les volumes finis et positifs comptent (au moins `VALIDES_MIN` sur 20), et
la participation n'est pas bornée : un ordre de plus d'un ADV s'exécute sur plusieurs
séances, la loi en racine sur la quantité totale reste l'approximation standard.
`participation()` publie la distribution pour qu'une saturation se VOIE.
"""

from __future__ import annotations

from bisect import bisect_left

import numpy as np

FENETRE = 20
VALIDES_MIN = 15               # volumes finis et > 0 exigés sur les 20 séances
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
        if not np.isfinite(cc).all() or (cc <= 0).any():
            return None
        ok = vv[np.isfinite(vv) & (vv > 0)]
        if ok.size < VALIDES_MIN:
            return None
        sigma = float((cc[1:] / cc[:-1] - 1.0).std(ddof=1))
        if not np.isfinite(sigma) or sigma <= 0:
            return None
        return float(ok.mean()), sigma


def impact(q: float, adv: float, sigma: float, y: float) -> float:
    """Impact d'un côté, en fraction du notionnel : Y · σ · √(q / ADV), NON borné."""
    if q <= 0 or adv <= 0 or sigma <= 0:
        return 0.0
    return float(y * sigma * (q / adv) ** 0.5)


def participation(ars: list[dict], params: list) -> dict:
    """Distribution de q / ADV (achat et vente) au capital du rejeu."""
    x = np.asarray([ar["q"] / adv for ar, p in zip(ars, params, strict=True)
                    for adv, _ in p])
    if x.size == 0:
        return {"n": 0}
    return {"n": int(x.size), "mediane": float(np.median(x)),
            "p90": float(np.quantile(x, 0.9)), "max": float(x.max()),
            "part_sup_1pct": float((x > 0.01).mean()),
            "part_sup_100pct": float((x > 1.0).mean())}


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
            "participation": participation(a, p),
            "hypothese": "exécution étalée sur la séance ; Y non calibré"}
