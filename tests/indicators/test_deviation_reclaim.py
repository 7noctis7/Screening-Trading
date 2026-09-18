"""Déviation → reclaim → consolidation : la géométrie, et rien d'autre.

CE QUE CES TESTS TIENNENT, dans l'ordre de ce qui coûterait le plus cher à rater :

  1. LE POINT-IN-TIME. Une fonction évaluée à `i` ne doit rien lire après `i`. C'est la
     propriété qui distingue un détecteur d'un raconteur d'histoires, et elle ne se voit
     pas à la lecture — on la MESURE en tronquant la série.
  2. L'ÉQUIVALENCE du précalcul de pivots. L'optimisation qui rend le banc exécutable
     est aussi la porte par laquelle le look-ahead entrerait : elle doit rendre
     exactement le même résultat que le rescan, barre par barre.
  3. L'ORDRE des états, et l'extrême de la DÉVIATION — un sweep à 95 suivi d'une barre à
     97 doit invalider sous 95, sinon le stop est plus serré que le creux réellement
     balayé et le reward/risk est flatté par construction.
  4. AUCUN NIVEAU INVENTÉ : ce que la structure ne fournit pas vaut None.

Barres SYNTHÉTIQUES, et c'est le seul endroit où le dépôt l'autorise : on valide ici la
MATH du détecteur, pas son pouvoir prédictif. Ce dernier se mesure sur l'historique réel
(`scripts/deviation_reclaim_lab.py`), et sur lui seul.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from packages.indicators.deviation_reclaim import (
    CONSOLIDATION_CONFIRMED,
    DEVIATION_DETECTED,
    PIVOT,
    RECLAIM_CONFIRMED,
    SEARCHING,
    etat,
    pivots_causaux,
    zone_support,
)


@dataclass
class B:
    high: float
    low: float
    close: float
    volume: float = 1e6
    ts: str = "2026-01-01"


def _plat(n: int, lo: float = 102.0) -> list[B]:
    return [B(lo + 3, lo, lo + 1) for _ in range(n)]


def _serie() -> list[B]:
    """Deux creux à ~100, une déviation à 95, un reclaim, puis l'acceptation."""
    b = _plat(8) + [B(103, 100.0, 101.5)] + _plat(8) + [B(103, 100.2, 101.5)] + _plat(8)
    b += [B(101.0, 95.0, 96.0), B(103.0, 97.0, 102.0)]
    return b + _plat(6, lo=101.5)


def _aleatoire(n: int = 400, graine: int = 3) -> list[B]:
    rng = random.Random(graine)
    px, out = 100.0, []
    for _ in range(n):
        px *= 1 + rng.gauss(0, 0.015)
        out.append(B(px * 1.01, px * 0.99, px))
    return out


# ─── 1. Point-in-time ──────────────────────────────────────────────────────────────

def test_l_etat_a_i_ne_depend_PAS_des_barres_futures():
    """LE test de ce module. On évalue `i` sur la série entière, puis sur la série
    TRONQUÉE à `i` : les deux doivent coïncider. S'ils diffèrent, le détecteur lit
    l'avenir — et tout ce qu'il mesurera ensuite sera un mirage."""
    b = _aleatoire()
    for i in range(30, len(b), 7):
        assert etat(b, i) == etat(b[:i + 1], i), f"barre {i} : lecture du futur"


def test_une_barre_ajoutee_APRES_i_ne_change_rien():
    """Formulation complémentaire : allonger la série ne doit pas réécrire le passé."""
    b = _serie()
    avant = etat(b, len(b) - 1)
    apres = etat([*b, B(200, 190, 195)], len(b) - 1)
    assert avant == apres


# ─── 2. Le précalcul des pivots est une optimisation, pas un raccourci ─────────────

def test_le_precalcul_donne_EXACTEMENT_le_meme_etat():
    b = _aleatoire()
    piv = pivots_causaux(b, PIVOT)
    for i in range(20, len(b), 3):
        assert etat(b, i) == etat(b, i, pivots=piv), f"divergence à {i}"


# ─── 3. La machine à états ────────────────────────────────────────────────────────

def test_les_etats_s_enchainent_dans_l_ORDRE():
    b = _serie()
    vus = [etat(b, i)["etat"] for i in range(len(b))]
    rang = {SEARCHING: 0, DEVIATION_DETECTED: 1, RECLAIM_CONFIRMED: 2,
            CONSOLIDATION_CONFIRMED: 3}
    atteints = [rang[e] for e in vus if e in rang]
    assert max(atteints) == 3, "la consolidation doit être atteinte"
    premier = {r: atteints.index(r) for r in (1, 2, 3)}
    assert premier[1] < premier[2] < premier[3], "déviation avant reclaim avant conso"


def test_l_invalidation_est_l_EXTREME_de_l_episode_pas_sa_derniere_barre():
    """Le sweep descend à 95 puis la barre suivante fait 97 — toutes deux sous la zone.
    Invalider à 97 donnerait un stop plus serré que le creux réellement balayé : un
    reward/risk amélioré par une erreur de définition, ce qui est le pire des deux."""
    b = _serie()
    e = etat(b, len(b) - 1)
    assert e["deviation"]["extreme"] == 95.0
    assert e["deviation"]["barres"] == 2
    assert e["invalidation"] == 95.0


def test_une_MECHE_au_dessus_de_la_zone_ne_vaut_pas_reclaim():
    """« Une simple mèche au-dessus de la zone ne suffit pas » : le reclaim se lit sur
    la CLÔTURE, comme l'invalidation. Sans ça, la moindre barre volatile récupère."""
    b = _plat(8) + [B(103, 100.0, 101.5)] + _plat(8) + [B(103, 100.2, 101.5)] + _plat(8)
    b += [B(101.0, 95.0, 96.0)]
    b += [B(103.0, 94.0, 96.5)] * 6          # mèches hautes, clôtures SOUS la zone
    assert etat(b, len(b) - 1)["etat"] == DEVIATION_DETECTED


def test_une_cassure_DURABLE_n_est_pas_une_deviation():
    """Filtre anti-faux-positif n°1 : passé le délai, ce n'est plus une absorption."""
    b = _plat(8) + [B(103, 100.0, 101.5)] + _plat(8) + [B(103, 100.2, 101.5)] + _plat(8)
    b += [B(96, 90, 92)] * 20                # vingt barres sous la zone
    b += [B(104, 101, 103)] * 5              # remontée bien trop tardive
    assert etat(b, len(b) - 1)["etat"] != CONSOLIDATION_CONFIRMED


def test_une_cloture_sous_l_invalidation_casse_la_consolidation():
    b = _serie()
    b = [*b, B(96, 90, 91)]                  # clôture sous l'extrême du sweep
    assert etat(b, len(b) - 1)["etat"] != CONSOLIDATION_CONFIRMED


# ─── 4. Aucun niveau inventé ──────────────────────────────────────────────────────

def test_une_zone_exige_PLUSIEURS_reactions():
    """Un creux isolé n'est pas un support : c'est un accident. Sans ce seuil, le motif
    se déclencherait sur n'importe quel bas local."""
    b = _plat(10) + [B(103, 100.0, 101.5)] + _plat(10)
    assert zone_support(b, len(b) - 1) is None


def test_la_zone_SURVIT_a_sa_propre_deviation():
    """CORRECTIF DE CONCEPTION. En ancrant sur le creux le PLUS RÉCENT, la déviation —
    une fois confirmée comme pivot — devenait l'ancre, ne réunissait personne, et la
    zone disparaissait à l'instant précis où le motif devenait intéressant."""
    b = _serie() + _plat(8, lo=101.5)
    z = zone_support(b, len(b) - 1)
    assert z is not None and z["reactions"] >= 2
    assert z["low"] == 100.0 and z["high"] == 100.2


def test_ce_que_la_structure_ne_fournit_pas_vaut_None():
    """« Ne définis pas une cible arbitraire pour améliorer le ratio. » Sans pivot
    haut au-dessus du prix, résistance et cible macro valent None — pas un
    nombre poli."""
    b = _serie()
    e = etat(b, len(b) - 1)
    assert e["confirmation"] is None and e["macro"] is None


def test_l_historique_trop_court_se_DIT():
    e = etat(_plat(5), 4)
    assert e["etat"] == SEARCHING and "insuffisant" in e["motif"]


def test_aucun_score_ni_recommandation_n_est_produit():
    """Le module refuse de noter et de recommander : des poids choisis à la main
    transforment une opinion en chiffre, et un composant non certifié qui dit d'acheter
    est un P0 (`vault/15_CERTIFICATION.md`)."""
    e = etat(_serie(), len(_serie()) - 1)
    interdits = {"score", "confidence", "confidence_score", "action", "final_action",
                 "rr", "reward_risk"}
    assert not (set(e) & interdits), f"champ d'opinion : {set(e) & interdits}"
