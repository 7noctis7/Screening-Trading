"""Détection et ajustement des SPLITS — sans jamais deviner.

Le problème. Le garde-fou anti-glitch écartait un titre dès qu'une séance bougeait de plus de
150 %. Un regroupement 1:10 (+900 %) est donc bien attrapé ; un SPLIT 4:1, qui fait −75 %, passe
sous le seuil et corrompt tous les rendements qui le traversent. Le filtre protégeait du cas rare
et laissait passer le fréquent — et les splits frappent précisément les valeurs qui ont beaucoup
monté, c'est-à-dire celles que le momentum sélectionne.

Le piège de la correction. Un ajustement appliqué à tort à un VRAI krach est pire que le mal :
il transforme une perte réelle en continuité de prix, donc en rendement inventé. Un −50 % de
marché existe (Wirecard, Lehman, une biotech dont l'essai échoue). On ne peut donc pas ajuster
sur le seul ratio de prix.

La règle retenue. On n'ajuste que si DEUX signaux concordent :
  1. le ratio de prix est proche d'une fraction simple (1/2, 1/3, 1/4, 1/5, 1/10, 2/3, 3/4…) —
     un krach tombe rarement pile sur 0,250 ;
  2. le VOLUME se multiplie dans le sens inverse — un split 4:1 quadruple le nombre de titres,
     donc les volumes échangés changent d'échelle. Un krach fait exploser le volume en valeur,
     pas d'un facteur qui égale le ratio de prix.

Sans volume exploitable, on NE TRANCHE PAS : on signale le candidat et on laisse l'appelant
écarter le titre. Un titre écarté coûte une occasion ; un rendement inventé coûte la confiance
dans tous les autres.
"""

from __future__ import annotations

from dataclasses import dataclass

# Fractions de split usuelles (prix APRÈS / prix AVANT). 2:1 → 0,5 ; 3:1 → 1/3 ; etc.
# Les regroupements (ratios > 1) sont déjà attrapés par le seuil de variation extrême.
RATIOS_USUELS: tuple[float, ...] = (1 / 2, 1 / 3, 1 / 4, 1 / 5, 1 / 6, 1 / 8, 1 / 10, 1 / 20,
                                    2 / 3, 3 / 4, 2 / 5, 3 / 2, 2.0, 3.0, 4.0, 5.0, 10.0)
# Tolérance relative autour d'une fraction usuelle. 2 % laisse passer le décalage normal entre
# la clôture de la veille et l'ouverture ajustée, sans accepter n'importe quel ratio.
TOLERANCE = 0.02
# En deçà, la variation reste du domaine du marché : on ne cherche même pas un split.
SEUIL_VARIATION = 0.30
# Le volume doit être PROCHE de l'échelle attendue (facteur ×/÷ 1,5)…
TOLERANCE_VOLUME = 1.5
# …ET franchement DIFFÉRENT de « inchangé ». Sans cette seconde condition, une bande large
# autour de l'attendu englobe le ratio 1,0 : un volume qui n'a pas bougé « confirmait » alors un
# split 2:1. Un volume inchangé est justement la signature d'un mouvement de marché.
MIN_ECART_VOLUME = 1.3


@dataclass(frozen=True)
class Candidat:
    """Un pas suspect. `certain` = les deux signaux concordent, donc ajustable sans deviner."""
    index: int                  # le split se situe entre index et index+1
    ratio: float                # prix après / prix avant
    ratio_usuel: float          # la fraction simple la plus proche
    confirme_volume: bool
    certain: bool
    motif: str


def _fraction_proche(ratio: float) -> float | None:
    """La fraction usuelle à moins de TOLERANCE du ratio, ou None."""
    for r in RATIOS_USUELS:
        if abs(ratio - r) <= TOLERANCE * r:
            return r
    return None


def detecter(closes: list[float], volumes: list[float] | None = None) -> list[Candidat]:
    """Repère les pas attribuables à un split. Liste vide = rien de suspect."""
    out: list[Candidat] = []
    if len(closes) < 2:
        return out
    vol = volumes if volumes and len(volumes) == len(closes) else None
    for i in range(len(closes) - 1):
        avant, apres = closes[i], closes[i + 1]
        if avant <= 0 or apres <= 0:
            continue
        ratio = apres / avant
        if abs(ratio - 1.0) < SEUIL_VARIATION:
            continue
        usuel = _fraction_proche(ratio)
        if usuel is None:
            continue                      # variation forte mais ratio quelconque → marché
        confirme = False
        if vol is not None and vol[i] > 0 and vol[i + 1] > 0:
            # Un split divise le prix par k et multiplie le nombre de titres par k : le volume
            # en TITRES change donc d'échelle dans le sens inverse du prix.
            attendu = 1.0 / usuel
            observe = vol[i + 1] / vol[i]
            proche = attendu / TOLERANCE_VOLUME <= observe <= attendu * TOLERANCE_VOLUME
            a_bouge = not (1.0 / MIN_ECART_VOLUME <= observe <= MIN_ECART_VOLUME)
            confirme = proche and a_bouge
        certain = confirme
        motif = ("prix et volume concordent (ratio "
                 f"{usuel:.4g}) — split" if certain else
                 f"ratio proche de {usuel:.4g} mais volume non confirmé — candidat, non tranché")
        out.append(Candidat(i, ratio, usuel, confirme, certain, motif))
    return out


def ajuster(closes: list[float], volumes: list[float] | None = None) -> tuple[list[float], list[Candidat]]:
    """Rétropropage les splits CERTAINS pour rendre la série continue.

    Convention usuelle : on ajuste le PASSÉ sur l'échelle actuelle (les cours récents ne bougent
    pas), pour qu'un prix affiché aujourd'hui reste celui du marché. Les candidats non confirmés
    ne sont PAS appliqués : ils sont renvoyés pour que l'appelant décide d'écarter le titre.
    """
    cands = detecter(closes, volumes)
    ajustes = list(closes)
    for c in cands:
        if not c.certain:
            continue
        # Tout ce qui précède le split est ramené à l'échelle post-split.
        for j in range(c.index + 1):
            ajustes[j] *= c.ratio_usuel
    return ajustes, cands


def exploitable(closes: list[float], volumes: list[float] | None = None) -> tuple[bool, str]:
    """La série peut-elle servir telle quelle ? Décision unique pour les appelants.

    Renvoie (False, motif) dès qu'un candidat non tranché subsiste : mieux vaut un titre écarté
    qu'un rendement inventé au milieu de l'historique.
    """
    doutes = [c for c in detecter(closes, volumes) if not c.certain]
    if doutes:
        c = doutes[0]
        return False, f"split non tranché au pas {c.index} : {c.motif}"
    return True, ""
