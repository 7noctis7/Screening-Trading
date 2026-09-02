"""Capitulation sur volume : prix sous TOUTES les moyennes, puis volume qui revient.

L'INTÉRÊT DE CE SIGNAL EST SA DIRECTION. La production exige cours > MM50 croissante ;
celui-ci exige cours < MM20 < MM50 < MM100 < MM200. C'est le premier candidat de la
série STRUCTURELLEMENT opposé au flux existant, et c'est la seule propriété qui fasse
monter un Sharpe combiné : un flux corrélé à 0,7 n'apporte rien, quel que soit son
mérite propre.

RÉSOLUTION HEBDOMADAIRE, DEPUIS DES BARRES QUOTIDIENNES. La base ne stocke que du
quotidien. On agrège, et on n'utilise QUE les semaines CLOSES : la semaine en cours est
partielle, et son volume cumulé n'est pas comparable à celui d'une semaine entière.
Traiter une semaine partielle comme une semaine pleine sous-estimerait son volume et
raterait le pic — ou, pire selon le sens, en inventerait un.

DEUX POINTS DE LA SPÉCIFICATION QUI NE SE CODENT PAS TELS QUELS, et qui sont donc
paramétrés plutôt que devinés :

1. « le prix est dans la zone de bon prix (proche des plus bas) » n'a pas de définition
   exécutable. Retenu ici : la clôture est dans les `part_du_bas` % du plus bas des
   `fenetre_bas` dernières semaines. Le seuil est un paramètre, pas une vérité.

2. « clôturer si le prix repasse au-dessus de la MM20 » CONTREDIT la prise de bénéfice à
   3R. L'entrée exige cours < MM20 ; un objectif à +3R depuis un plus bas est le
   plus souvent AU-DESSUS de la MM20. La sortie couperait donc les gagnants avant
   l'objectif — le défaut mesuré et retiré le 02/09 sur le stop suiveur.
   Ce n'est pas un avis : le paramètre existe pour que ce soit MESURÉ.
"""

from __future__ import annotations

MOYENNES = (20, 50, 100, 200)
FENETRE_VOLUME = 20
K_ECARTS = 2.0                   # pic = moyenne + k écarts-types
CONFIRMATIONS = 3                # semaines de volume croissant après le pic
FENETRE_BAS = 52
PART_DU_BAS = 0.15               # « proche des plus bas » : 15 % au-dessus du plus bas


class BarreHebdo:
    """Semaine CLOSE, agrégée depuis des barres quotidiennes."""

    __slots__ = ("ts", "open", "high", "low", "close", "volume")

    def __init__(self, ts, o, h, b, c, v):
        self.ts, self.open, self.high = ts, o, h
        self.low, self.close, self.volume = b, c, v


def _lundi(ts):
    d = ts.date() if hasattr(ts, "date") else ts
    return d.toordinal() - d.weekday()


def hebdomadaire(barres: list, inclure_partielle: bool = False) -> list[BarreHebdo]:
    """Agrège en semaines. La dernière est ÉCARTÉE si elle est incomplète.

    « Incomplète » se juge sur le calendrier, pas sur le nombre de barres : un férié
    fait une semaine de 4 séances pourtant close. On écarte donc la dernière
    semaine dès lors que la série s'arrête avant son vendredi — seul critère disponible
    sans calendrier de bourse.
    """
    if not barres:
        return []
    groupes: dict[int, list] = {}
    for b in barres:
        groupes.setdefault(_lundi(b.ts), []).append(b)
    semaines = []
    for cle in sorted(groupes):
        g = groupes[cle]
        semaines.append(BarreHebdo(
            g[-1].ts, float(g[0].open), max(float(x.high) for x in g),
            min(float(x.low) for x in g), float(g[-1].close),
            sum(float(getattr(x, "volume", 0.0) or 0.0) for x in g)))
    if not inclure_partielle and semaines:
        derniere = barres[-1].ts
        jour = derniere.date() if hasattr(derniere, "date") else derniere
        if jour.weekday() < 4:                    # série arrêtée avant vendredi
            semaines.pop()
    return semaines


def _moyenne(valeurs: list[float], n: int) -> float | None:
    return sum(valeurs[-n:]) / n if len(valeurs) >= n else None


def empilement_baissier(closes: list[float], moyennes=MOYENNES) -> bool:
    """cours < MM20 < MM50 < MM100 < MM200 — l'inverse exact du filtre de production."""
    mm = [_moyenne(closes, n) for n in moyennes]
    if any(m is None for m in mm):
        return False
    return closes[-1] < mm[0] and all(mm[i] < mm[i + 1] for i in range(len(mm) - 1))


def pic_de_volume(volumes: list[float], i: int, fenetre: int = FENETRE_VOLUME,
                  k: float = K_ECARTS) -> bool:
    """Volume > moyenne + k écarts-types sur les `fenetre` semaines PRÉCÉDENTES.

    La fenêtre exclut la semaine testée : l'inclure ferait entrer le pic dans sa propre
    référence, ce qui relève le seuil et rend le pic plus dur à détecter à mesure qu'il
    est plus fort — un biais silencieux et du mauvais côté.
    """
    if i < fenetre or i >= len(volumes):
        return False
    passe = volumes[i - fenetre:i]
    moy = sum(passe) / fenetre
    var = sum((v - moy) ** 2 for v in passe) / fenetre
    return volumes[i] > moy + k * (var ** 0.5)


def volume_croissant(volumes: list[float], depuis: int, n: int = CONFIRMATIONS,
                     strict: bool = False) -> bool:
    """Le volume REVIENT après le pic — deux lectures, et le choix n'est pas cosmétique.

    La spécification proposait une alternative : « chaque bougie a un volume supérieur
    ou égal à la précédente, OU la moyenne mobile courte du volume est en pente
    ascendante ».

    LA PREMIÈRE BRANCHE REND LA CONJONCTION VIDE, et c'est mesuré, pas supposé : après
    un pic à deux écarts-types, exiger trois dépassements successifs d'un extrême
    arrive dans 0,008 % des cas (200 000 tirages). Combinée aux trois autres
    conditions, elle ne se déclenche JAMAIS — zéro signal sur 2 240 barres, toutes
    configurations confondues. Un setup qui ne se déclenche jamais n'est pas sélectif,
    il est mort.

    LA SECONDE BRANCHE dit ce que la thèse veut dire : après la capitulation,
    l'activité NE RETOMBE PAS. On la lit comme un volume moyen post-pic supérieur à
    celui d'avant — l'intérêt persiste, sans exiger qu'il croisse à chaque barre.

    `strict=True` garde la lecture littérale, pour qu'elle reste mesurable plutôt que
    seulement critiquée.
    """
    fin = depuis + n
    if fin >= len(volumes):
        return False
    if strict:
        return all(volumes[k] >= volumes[k - 1] for k in range(depuis + 1, fin + 1))
    # La branche par moyenne compare l'APRÈS à l'AVANT : elle seule exige un historique
    # antérieur au pic. Étendre ce garde à la branche stricte la rendrait fausse près du
    # début de série — un « False » qui ressemblerait à un refus, alors que c'est un
    # manque de données.
    if depuis < n:
        return False
    apres = volumes[depuis + 1:fin + 1]
    avant = volumes[depuis - n:depuis]
    return sum(apres) / len(apres) > sum(avant) / len(avant)


def proche_des_bas(bas: list[float], close: float,
                   fenetre: int = FENETRE_BAS, part: float = PART_DU_BAS) -> bool:
    """« Zone de bon prix » — définie : une règle non définie ne se teste pas."""
    if len(bas) < fenetre:
        return False
    plancher = min(bas[-fenetre:])
    return plancher > 0 and close <= plancher * (1.0 + part)


def signal_sur(barres: list, i: int, confirmations: int = CONFIRMATIONS,
               k: float = K_ECARTS, part_du_bas: float = PART_DU_BAS,
               moyennes=MOYENNES, fenetre_bas: int = FENETRE_BAS) -> bool:
    """Vrai à la CLÔTURE de la barre `i`, qui confirme la reprise de volume.

    INDÉPENDANT DE LA RÉSOLUTION : `barres` peut être hebdomadaire ou quotidien. Mais
    changer de résolution à PÉRIODES ÉGALES ne donne pas « le même signal avec plus de
    points » — c'est un AUTRE signal. MM200 hebdomadaire couvre 3,8 ans, donc un marché
    baissier séculaire ; MM200 quotidienne couvre 9,5 mois, donc une correction
    intermédiaire. Les deux méritent d'être mesurés, mais jamais confondus.

    Et à HORIZON ÉGAL (MM1000 quotidienne ≈ MM200 hebdo), passer au quotidien ne
    multiplie PAS l'information par cinq : ce sont les mêmes épisodes observés plus
    souvent, et le `n_effectif` corrigé de la dépendance bougerait à peine. Le gain
    statistique ne vient que des périodes plus courtes, qui produisent des épisodes plus
    nombreux — pas de la résolution en elle-même.

    ANTI-FUITE, ET ELLE EST STRUCTURELLE. Tout est lu sur `semaines[:i + 1]` : la
    fonction n'a littéralement pas accès à ce qui suit. Le pic est cherché exactement
    `confirmations` semaines AVANT `i`, et la confirmation se lit sur les semaines
    intermédiaires — la décision tombe donc à la clôture de la semaine `i`.

    Cette forme existe pour être PRÉCALCULABLE. Repartir des barres quotidiennes à
    chaque évaluation obligerait à ré-agréger 1 400 jours par appel, ce qui rend le
    candidat inexécutable sur 786 titres. Le contenu de la décision est identique ;
    seul son coût change.
    """
    # FENÊTRE BORNÉE, ET CE N'EST PAS UN DÉTAIL DE PERFORMANCE. Découper `barres[:i+1]`
    # copie tout le préfixe à chaque appel : évalué barre par barre sur 2 760 jours et
    # 786 titres, c'est un O(n²) : quatre minutes là où il en faut quinze secondes.
    # Le besoin réel est borné — la plus longue moyenne, la fenêtre des plus bas, ou la
    # fenêtre de volume plus les confirmations — donc on ne copie que cela.
    besoin = max(max(moyennes) + confirmations + 2, fenetre_bas,
                 FENETRE_VOLUME + confirmations + 2)
    debut = i - besoin + 1
    if i < 0 or i >= len(barres) or debut < 0:
        return False
    vue = barres[debut:i + 1]
    closes = [s.close for s in vue]
    volumes = [s.volume for s in vue]
    if not empilement_baissier(closes, moyennes):
        return False
    i_pic = len(vue) - 1 - confirmations
    if not pic_de_volume(volumes, i_pic, k=k):
        return False
    if not volume_croissant(volumes, i_pic, confirmations):
        return False
    return proche_des_bas([s.low for s in vue], closes[-1],
                          fenetre=fenetre_bas, part=part_du_bas)


def signal_hebdo(semaines: list, i: int, confirmations: int = CONFIRMATIONS,
                 k: float = K_ECARTS, part_du_bas: float = PART_DU_BAS) -> bool:
    """Résolution HEBDOMADAIRE, périodes de la spécification."""
    return signal_sur(semaines, i, confirmations, k, part_du_bas)


def signal(barres: list, confirmations: int = CONFIRMATIONS,
           k: float = K_ECARTS, part_du_bas: float = PART_DU_BAS) -> bool:
    """Même décision depuis des barres QUOTIDIENNES : agrège puis délègue."""
    sem = hebdomadaire(barres)
    return signal_hebdo(sem, len(sem) - 1, confirmations, k, part_du_bas)
