"""Ce qu'un tableau de bord n'a PAS le droit de publier — contradictions, pas seuils.

CE QUI EST ARRIVÉ LE 04/09. Le site a publié, et le téléphone a affiché : gain total
−100 %, CAGR −100 %, pire baisse −100 %… avec un Sharpe de **0,25** et un Sortino de
**0,18**. Ces deux moitiés ne peuvent pas être vraies ensemble : un capital réduit à
zéro donne un Sharpe franchement négatif. C'est l'utilisateur qui l'a vu.

Le gate de publication existait déjà et vérifiait la présence des fichiers, leur taille
et leur fraîcheur. Il ne REGARDAIT JAMAIS LES NOMBRES. Un dump complet, volumineux et
daté d'aujourd'hui passait au vert en annonçant la ruine.

POURQUOI DES CONTRADICTIONS ET NON DES SEUILS. « CAGR < −50 % » serait un jugement : une
stratégie peut légitimement perdre beaucoup, et un gate qui refuse les mauvaises
nouvelles finit par cacher les vraies. Une CONTRADICTION ne dépend d'aucune
opinion : si le capital est anéanti, aucun ratio calculé sur les mêmes rendements
ne peut être positif. Le gate ne juge pas la performance, il refuse l'impossible.

LES DEUX RÈGLES, ET LA SECONDE VAUT MIEUX QUE LA PREMIÈRE :

  1. Anéantissement + ratio positif → impossible. Attrape le SYMPTÔME.
  2. Trou (`null`) dans une courbe d'équity publiée → attrape la CAUSE. `_clean`
     convertit NaN en `null` pour que le JSON reste valide ; c'est le bon geste,
     mais il rend le défaut invisible en aval — le front lit un trou comme un zéro.
     Une courbe percée n'est pas une courbe, avant même de savoir ce que le trou dit.
"""

from __future__ import annotations

import math
from typing import Any

# Sous ce seuil, le capital est considéré comme ANÉANTI. Ce n'est pas un jugement sur la
# performance : à −99,9 %, il ne reste pas de quoi qu'un ratio positif ait un sens.
ANEANTISSEMENT = -0.999


def _fini(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def trous_dans_courbe(courbe: object) -> int:
    """Nombre de points non exploitables (`null`, NaN, texte) dans une courbe publiée.

    Une courbe d'équity est une suite de montants. Un trou n'y est pas une donnée
    manquante bénigne : le front l'affiche comme zéro, et un zéro au milieu d'une
    equity signifie faillite. Refuser de publier vaut mieux qu'une ruine imaginaire.

    ON FILTRE PAR TYPE, PAS PAR NOM DE CLÉ (correctif du 04/09). La première version
    faisait `if not courbe` puis itérait : appelée sur `spec = {"qqq": 0.5}` — où
    `qqq` désigne le POIDS du cœur et non sa courbe — elle levait
    `TypeError: 'float' object is not iterable` et **le gate a bloqué le déploiement
    pour la mauvaise raison**. J'avais deviné des noms de clés au lieu de les vérifier
    sur le payload réel ; or un nom peut toujours resservir ailleurs avec un autre
    sens. Le type, lui, ne ment pas : ce qui n'est pas une liste n'est pas une courbe.

    Un gate qui plante est aussi nuisible qu'un gate absent — il apprend qu'on peut
    l'ignorer, et le premier réflexe devant un build rouge inexpliqué est de le
    désactiver."""
    if not isinstance(courbe, list) or not courbe:
        return 0
    return sum(1 for x in courbe if not _fini(x))


def contradictions(stats: dict | None) -> list[str]:
    """Énoncés impossibles dans un bloc de statistiques. Liste vide = rien d'incohérent.

    On ne vérifie QUE ce qui ne dépend d'aucune opinion. Deux chiffres qui déplaisent
    passent ; deux chiffres qui ne peuvent pas coexister sont refusés."""
    if not stats:
        return []
    out = []
    cagr, total = stats.get("cagr"), stats.get("total_return")
    for nom, v in (("CAGR", cagr), ("gain total", total)):
        if _fini(v) and v <= ANEANTISSEMENT:
            for ratio in ("sharpe", "sortino"):
                rv = stats.get(ratio)
                if _fini(rv) and rv > 0:
                    out.append(
                        f"{nom} {v * 100:.1f} % (capital anéanti) mais {ratio} "
                        f"{rv:+.2f} > 0 — les deux ne peuvent être vrais ensemble")
    mdd = stats.get("max_drawdown")
    if _fini(mdd) and _fini(total) and mdd <= ANEANTISSEMENT and total > ANEANTISSEMENT:
        out.append(f"pire baisse {mdd * 100:.1f} % (capital anéanti) mais gain total "
                   f"{total * 100:.1f} % — une equity à zéro ne remonte pas")
    return out


def auditer(payload: dict, *, chemin: str = "") -> list[str]:
    """Parcourt un payload publié et renvoie TOUS les motifs de refus trouvés.

    Récursif : les blocs de stats et les courbes sont imbriqués à des profondeurs
    variables selon les pages, et une règle qui ne regarde qu'un chemin connu rate le
    prochain endroit où le défaut apparaîtra."""
    motifs: list[str] = []
    if isinstance(payload, dict):
        motifs += [f"{chemin or 'racine'} : {m}" for m in contradictions(payload)]
        for cle in ("equity", "curve", "preset", "qqq", "megacap", "sector_mom"):
            n = trous_dans_courbe(payload.get(cle))
            if n:
                motifs.append(f"{chemin}/{cle} : {n} point(s) non exploitable(s) "
                              "dans une courbe publiée")
        for k, v in payload.items():
            if isinstance(v, dict):
                motifs += auditer(v, chemin=f"{chemin}/{k}")
    return motifs
