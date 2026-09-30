"""Bande d'inaction ADAPTATIVE — coût d'un ordre contre coût de l'écart de suivi.

La production rééquilibre dès qu'une ligne s'écarte de sa cible de plus de 0,5 % du
capital, quels que soient la volatilité du titre et le prix de l'ordre. Un titre calme et
bon marché à négocier est traité comme une crypto volatile et chère.

LE MODÈLE (stylisé, dérivé ici plutôt qu'emprunté). Entre deux ordres, le poids d'une
ligne dérive comme une marche aléatoire de variance annuelle s² ≈ (w(1−w)σ)², où σ est la
volatilité du titre. On n'agit que lorsque l'écart sort de ±h :
  * coût de l'écart de suivi par an ≈ (γ/2)·E[(w−w*)²] ≈ γ·h²/6 (écart ~ uniforme sur ±h) ;
  * une marche de variance s² sort de ±h environ s²/h² fois par an, et chaque sortie
    négocie ~h au coût aller simple c : coût de négociation ≈ c·s²/h.
Minimiser γh²/6 + c·s²/h donne h* = (3·c·s²/γ)^(1/3) — la loi en racine cubique connue
des modèles à coûts proportionnels (Davis-Norman, Leland) : doubler la bande exige un
coût multiplié par huit.

CE QUI N'EST PAS CALIBRÉ. L'aversion γ à l'écart de suivi. Tant qu'une mesure sur données
réelles (`make preset-replay ARGS="--bande adaptative"`) ne l'a pas fixée, ce module ne
pilote PAS la production : il sert au rejeu, à comparer contre la bande fixe.
"""

from __future__ import annotations

import math
from bisect import bisect_right

BANDE_MIN_MONNAIE = 5.0       # même plancher que run_live._broker_targets
PLANCHER_DEFAUT = 0.001       # 0,1 % du capital : sous ce seuil, l'ordre est du bruit
PLAFOND_DEFAUT = 0.05         # jamais plus de 5 points de poids d'écart toléré
FENETRE_VOL = 63              # jours de cotation (≈ 3 mois)


def demi_largeur(poids: float, vol_annuelle: float, cout_aller: float, *,
                 aversion: float, plancher: float = PLANCHER_DEFAUT,
                 plafond: float = PLAFOND_DEFAUT) -> float:
    """Demi-largeur h* de la bande, en FRACTION du capital. Cas dégénérés → plancher.

    >>> round(demi_largeur(0.08, 0.30, 0.0005, aversion=1.0, plancher=0.0), 5)
    0.00901
    """
    if not aversion > 0:
        raise ValueError(f"aversion doit être > 0 (reçu {aversion})")
    w = min(max(float(poids), 0.0), 1.0)
    if not (math.isfinite(vol_annuelle) and vol_annuelle > 0 and cout_aller > 0 and w > 0):
        return plancher
    s = w * (1.0 - w) * vol_annuelle
    h = (3.0 * cout_aller * s * s / aversion) ** (1.0 / 3.0)
    return min(max(h, plancher), plafond)


def bande_monnaie(poids: float, capital: float, vol_annuelle: float, cout_aller: float, *,
                  aversion: float) -> float:
    """Bande en monnaie pour `rebalance_plan.decider`, jamais sous 5 $."""
    h = demi_largeur(poids, vol_annuelle, cout_aller, aversion=aversion)
    return max(h * float(capital), BANDE_MIN_MONNAIE)


def vol_annuelle(prix: dict[str, float], jours: list[str], jour: str,
                 fenetre: int = FENETRE_VOL, par_an: float = 252.0) -> float:
    """Volatilité annualisée des rendements journaliers connus AU PLUS TARD le `jour`.

    `jours` = dates triées de `prix`. Moins de `fenetre` rendements → NaN (jamais deviné)."""
    fin = bisect_right(jours, jour)
    serie = [prix[j] for j in jours[max(0, fin - fenetre - 1):fin]]
    r = [serie[k + 1] / serie[k] - 1.0 for k in range(len(serie) - 1) if serie[k] > 0]
    if len(r) < fenetre:
        return float("nan")
    m = sum(r) / len(r)
    var = sum((x - m) ** 2 for x in r) / (len(r) - 1)
    return math.sqrt(var * par_an)
