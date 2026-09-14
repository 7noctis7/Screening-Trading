"""Un écart de moyenne est-il exploitable ? Quatre mesures, et elles peuvent dire non.

POURQUOI CE MODULE EXISTE SÉPARÉMENT. `regime_atr` répond à « les deux régimes
diffèrent-ils ». C'est une question de STATISTIQUE. Celle-ci en est une autre :
l'écart constaté est-il quelque chose qu'on peut jouer. Un t de Welch ne le dit pas,
et ce dépôt a déjà payé la confusion — `scripts/sizing_lab.py` a montré un système au
profit factor 1,15 qui tombait à **0,89** privé de ses cinq meilleurs trades sur 477.
Perdant. Le chiffre agrégé était vrai et la conclusion qu'on en tirait, fausse.

Les quatre questions, dans l'ordre où elles ferment le sujet :

1. **La moyenne ressemble-t-elle à la médiane ?** Un écart moyen de +4 % porté par une
   médiane à 0 décrit une loterie, pas un régime. On rend aussi le taux de gain.
2. **Que reste-t-il sans les meilleures ?** Si retirer 1 % des observations efface
   l'écart, on ne mesurait pas un régime : on mesurait quelques billets gagnants.
3. **Combien d'ÉPISODES, et non de journées ?** 458 journées peuvent être six crises.
   Des jours consécutifs d'une même secousse ne sont pas des tirages indépendants —
   le regroupement par date de `regime_atr` ne corrige pas ça, il corrige la
   corrélation transversale.
4. **Une seule année porte-t-elle le résultat ?** Mars 2020 suffit à colorer onze ans.

Aucune E/S. Aucun seuil de décision : ce module MESURE, l'appelant tranche.
"""

from __future__ import annotations

from datetime import date

ECART_EPISODE_J = 5       # au-delà, deux journées relèvent de secousses différentes
PART_ALERTE = 0.50        # un épisode ou une année qui porte la moitié du total


def distribution(xs: list[float]) -> dict:
    """Ce que la moyenne cache : médiane, taux de gain, queues.

    `ecart_moyenne_mediane` est le signal à lire en premier. Proche de zéro, la moyenne
    résume honnêtement. Très positif, elle est tirée par une poignée de valeurs — et
    c'est exactement la situation où un backtest paraît rentable et ne l'est pas.
    """
    n = len(xs)
    if n == 0:
        return {"n": 0, "moyenne": None, "mediane": None, "taux_gain": None,
                "p10": None, "p90": None, "ecart_moyenne_mediane": None}
    s = sorted(xs)
    moy = sum(s) / n
    med = _quantile(s, 0.5)
    return {"n": n, "moyenne": round(moy, 6), "mediane": round(med, 6),
            "taux_gain": round(sum(1 for x in s if x > 0) / n, 4),
            "p10": round(_quantile(s, 0.10), 6), "p90": round(_quantile(s, 0.90), 6),
            "ecart_moyenne_mediane": round(moy - med, 6)}


def _quantile(tries: list[float], q: float) -> float:
    """Interpolation linéaire sur une liste DÉJÀ triée."""
    if len(tries) == 1:
        return tries[0]
    pos = q * (len(tries) - 1)
    bas = int(pos)
    haut = min(bas + 1, len(tries) - 1)
    return tries[bas] + (pos - bas) * (tries[haut] - tries[bas])


def sans_les_meilleurs(xs: list[float], part: float = 0.01) -> dict:
    """La moyenne survit-elle au retrait des `part` meilleures observations ?

    Le test que `sizing_lab` a rendu obligatoire ici. On retire au moins UNE observation
    même quand la part arrondit à zéro : « retirer 1 % » d'un échantillon de 50 doit
    retirer quelque chose, sinon le contrôle passe sans rien contrôler.
    """
    n = len(xs)
    if n < 2:
        return {"disponible": False, "motif": "moins de deux observations"}
    k = max(1, int(round(n * part)))
    if k >= n:
        return {"disponible": False, "motif": f"retirer {k} sur {n} ne laisse rien"}
    s = sorted(xs)
    complet = sum(s) / n
    ampute = sum(s[:-k]) / (n - k)
    return {"disponible": True, "retirees": k, "part": part,
            "moyenne_complete": round(complet, 6), "moyenne_amputee": round(ampute, 6),
            "survit": ampute > 0 if complet > 0 else ampute < 0,
            "perte_relative": (round(1 - ampute / complet, 4)
                               if complet not in (0,) else None)}


def episodes(jours: list[str], ecart_max: int = ECART_EPISODE_J) -> list[list[str]]:
    """Regroupe des journées en secousses CONTIGUËS.

    Deux journées séparées de moins de `ecart_max` jours calendaires relèvent du même
    épisode. Le nombre d'épisodes est le vrai nombre de fois où le marché a répondu à
    la question posée — 458 journées de mars 2020 ne sont qu'une seule réponse.
    """
    propres = sorted({j for j in jours if j})
    if not propres:
        return []
    groupes: list[list[str]] = [[propres[0]]]
    for j in propres[1:]:
        if (_date(j) - _date(groupes[-1][-1])).days <= ecart_max:
            groupes[-1].append(j)
        else:
            groupes.append([j])
    return groupes


def _date(j: str) -> date:
    return date.fromisoformat(j[:10])


def concentration(observations: list[tuple[str, float]],
                  ecart_max: int = ECART_EPISODE_J) -> dict:
    """Le résultat tient-il à un épisode, ou à une année ?

    On somme les rendements par épisode et par année, puis on regarde la part du plus
    gros. Au-delà de `PART_ALERTE`, l'agrégat décrit un événement, pas un régime.
    """
    if not observations:
        return {"disponible": False, "motif": "aucune observation datée"}
    par_jour: dict[str, float] = {}
    par_an: dict[str, float] = {}
    for j, x in observations:
        par_jour[j] = par_jour.get(j, 0.0) + x
        par_an[j[:4]] = par_an.get(j[:4], 0.0) + x
    grappes = episodes(list(par_jour), ecart_max)
    totaux = [sum(par_jour[j] for j in g) for g in grappes]
    total = sum(totaux)
    plus_gros = max(totaux, key=abs, default=0.0)
    an_max = max(par_an.items(), key=lambda kv: abs(kv[1]), default=("", 0.0))
    return {"disponible": True, "n_jours": len(par_jour), "n_episodes": len(grappes),
            "jours_par_episode_median": _mediane_int([len(g) for g in grappes]),
            "part_plus_gros_episode": (round(plus_gros / total, 4) if total else None),
            "episode_dominant": _borne(max(zip(totaux, grappes, strict=True),
                                           key=lambda tg: abs(tg[0]))[1]),
            "annee_dominante": an_max[0],
            "part_annee_dominante": (round(an_max[1] / total, 4) if total else None),
            "par_annee": {a: round(v, 6) for a, v in sorted(par_an.items())}}


def _borne(groupe: list[str]) -> str:
    return groupe[0] if len(groupe) == 1 else f"{groupe[0]} → {groupe[-1]}"


def _mediane_int(xs: list[int]) -> int | None:
    if not xs:
        return None
    s = sorted(xs)
    return s[len(s) // 2]
