"""LA déviation baissière — une définition, quatre appelants.

LE PROBLÈME. Le dépôt calculait Sortino de TROIS façons différentes, et publiait les
trois côte à côte sans que rien ne l'indique :

    index_core._stats     RMS de min(r, 0) sur N total          ← la définition
    company_report        RMS de min(r, 0) sur N total          ← la définition
    metrics.sortino       écart-type des NÉGATIFS seuls          ← deux erreurs
    metrics.perf_summary  écart-type des NÉGATIFS seuls          ← deux erreurs
    analytics             écart-type de min(r, 0) sur N          ← une erreur

Deux ratios calculés autrement ne se comparent pas. Un Sortino de la page A et un
Sortino de la page B décrivaient le même portefeuille avec des chiffres différents, et
le lecteur n'avait aucun moyen de le savoir.

LA DÉFINITION (Sortino & Price, 1994). La déviation baissière est la racine de la
moyenne des CARRÉS des rendements sous le seuil, divisée par le nombre TOTAL
d'observations :

    DD = sqrt( Σ min(r_t − seuil, 0)² / N )

DEUX ERREURS FRÉQUENTES, et elles vont dans le même sens — surestimer le ratio :

  1. **Diviser par le nombre de rendements NÉGATIFS** au lieu de N. Un portefeuille qui
     ne baisse qu'un jour sur dix voit sa déviation multipliée par ~3, donc son Sortino
     divisé par 3… ou l'inverse selon le sens de l'erreur. Surtout : le ratio cesse de
     dépendre de la FRÉQUENCE des pertes, alors que c'est précisément ce que Sortino
     entend mesurer.
  2. **Soustraire la moyenne** (utiliser un écart-type plutôt qu'une RMS). Le seuil est
     déjà la référence ; retrancher la moyenne des pertes mesure leur dispersion autour
     d'elles-mêmes, pas leur ampleur.

MESURÉ (04/09) sur 2 520 rendements gaussiens (μ=0,05 %, σ=1,2 %, 46,6 % de séances
négatives) — les deux erreurs GONFLENT le Sortino, et plus que la note du backlog ne le
disait (elle annonçait 1,04×) :

    définition (RMS sur N)         0,008314    Sortino ×1,000
    écart-type des NÉGATIFS        0,007369    Sortino ×1,128
    écart-type de min(r,0) sur N   0,006979    Sortino ×1,191

Douze à dix-neuf pour cent de Sortino en plus selon la fonction appelée : assez pour
inverser un classement entre deux variantes, et invisible pour qui lit le chiffre.

Python pur, sans numpy : `analytics` et `company_report` s'en passent délibérément,
et la définition doit vivre là où TOUT le monde peut l'appeler.
"""

from __future__ import annotations

from collections.abc import Iterable


def deviation_baissiere(rendements: Iterable[float], seuil: float = 0.0) -> float:
    """Racine de la moyenne des carrés sous le `seuil`, sur le nombre TOTAL de points.

    Renvoie 0.0 si la série est vide ou si aucun rendement ne passe sous le seuil — un
    Sortino non défini, que les appelants traduisent en 0.0 comme pour le Sharpe."""
    r = [float(x) for x in rendements]
    n = len(r)
    if n == 0:
        return 0.0
    return (sum(min(x - seuil, 0.0) ** 2 for x in r) / n) ** 0.5


def sortino_annualise(rendements: Iterable[float], *, ppy: int = 252,
                      rf: float = 0.0) -> float:
    """Sortino annualisé. `rf` est un taux ANNUEL, ramené par période comme pour Sharpe.

    Séparé de la déviation pour que les appelants qui n'ont besoin que du dénominateur
    (ou d'une autre annualisation) ne dupliquent pas la définition."""
    r = [float(x) for x in rendements]
    if len(r) < 2:
        return 0.0
    dd = deviation_baissiere(r, seuil=0.0)
    if dd <= 0:
        return 0.0
    exces = sum(r) / len(r) - rf / ppy
    return exces / dd * (ppy ** 0.5)
