"""Le gate promouvait à +0,05 quand l'échantillon ne résolvait que ±0,118.

Mesuré le 31/08 puis laissé en l'état : `sharpe_diff.seuil_detectable` établit qu'onze
ans d'historique ne distinguent pas deux stratégies à mieux que ±0,118 de Sharpe. Le
labo IMPRIMAIT déjà cet avertissement — « le gate promeut à +0,05, soit 2× sous ce que
la donnée résout » — sans en tirer la conséquence : il continuait de promouvoir à 0,05.

Un seuil que la donnée ne peut pas honorer ne filtre rien. Il fabrique des
promotions au hasard, et chacune coûte ensuite du capital réel. Le remplacer
par un autre nombre choisi
(0,12) aurait juste déplacé l'arbitraire : le seuil DEVIENT la résolution mesurée de
l'échantillon, et se resserre tout seul quand l'historique s'allonge.

Trois choses gardées ici :
  1. le seuil suit la résolution de l'échantillon, il n'est plus constant ;
  2. il ne descend jamais sous le plancher d'exécution (un gain plus petit est mangé
     par les frais, même si la donnée savait le voir) ;
  3. l'entre-deux existe : une variante qui gagne plus que le plancher mais
     moins que la résolution n'est ni promue ni rejetée — elle est INDISTINCTE,
     et le dire est le seul verdict honnête.
"""

from __future__ import annotations

import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))

from scripts.preset_lab import PLANCHER_PROMOTION, seuil_de_promotion  # noqa: E402


def test_le_seuil_suit_la_resolution_de_l_echantillon() -> None:
    """Peu d'historique → seuil haut. Beaucoup → seuil bas. Jamais l'inverse."""
    court = {"n_steps": 132, "periods_per_year": 12.0, "sharpe": 1.0}     # 11 ans
    long = {"n_steps": 132 * 6, "periods_per_year": 12.0, "sharpe": 1.0}  # 66 ans
    s_court, _ = seuil_de_promotion(court)
    s_long, _ = seuil_de_promotion(long)
    assert s_court > s_long, (
        "Un échantillon plus long doit AUTORISER un seuil plus fin : c'est tout "
        "l'intérêt d'un seuil dérivé plutôt que choisi."
    )


def test_le_seuil_ne_promeut_plus_a_l_ancien_niveau() -> None:
    """Sur onze ans, +0,05 était un tirage au sort. Il ne doit plus suffire."""
    onze_ans = {"n_steps": 132, "periods_per_year": 12.0, "sharpe": 1.0}
    seuil, resolu = seuil_de_promotion(onze_ans)
    assert resolu > PLANCHER_PROMOTION, (
        "La résolution mesurée est retombée sous le plancher : vérifier "
        "`seuil_detectable` avant de conclure quoi que ce soit."
    )
    assert seuil > PLANCHER_PROMOTION, (
        "Le gate promeut de nouveau à +0,05 alors que la donnée ne résout pas si "
        "fin : les promotions redeviennent des tirages au sort."
    )


def test_le_plancher_d_execution_tient_meme_avec_un_gros_echantillon() -> None:
    """Un gain que les frais mangent ne se promeut pas, même bien mesuré."""
    enorme = {"n_steps": 100_000, "periods_per_year": 12.0, "sharpe": 1.0}
    seuil, resolu = seuil_de_promotion(enorme)
    assert resolu < PLANCHER_PROMOTION, (
        "Échantillon censé résoudre plus fin que le plancher."
    )
    assert seuil == PLANCHER_PROMOTION, (
        "Le plancher d'exécution a sauté : on promouvrait un gain plus petit que "
        "les frais qu'il coûte."
    )


def test_echantillon_trop_court_retombe_sur_le_plancher() -> None:
    """Moins de 30 pas : `seuil_detectable` n'a rien de fiable à dire."""
    attendu = (PLANCHER_PROMOTION, PLANCHER_PROMOTION)
    assert seuil_de_promotion({"n_steps": 12}) == attendu
