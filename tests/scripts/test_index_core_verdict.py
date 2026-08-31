"""Le sweep de la part de cœur ne doit pas transformer du bruit en recommandation.

`index_core_sweep` balaie cinq ratios (0/25/50/75/100 %) et affichait « → meilleur
Sharpe : X% ». Choisir le maximum de cinq essais EST une machine à surapprendre : le
maximum de n tirages bruités croît en racine de 2·ln(n), donc on trouve toujours un
gagnant, même sans aucun effet. Le verdict compare désormais chaque ratio à la part
ACTUELLE, de façon appariée, et dit quand l'écart n'est pas distinguable du bruit.
"""

import random

import pytest

from packages.research.sharpe_diff import comparer

sweep = pytest.importorskip("scripts.index_core_sweep")


def _courbe(seed: int, n: int = 1500, mu: float = 0.0004, sigma: float = 0.011):
    rng = random.Random(seed)
    eq, v = [100.0], 100.0
    for _ in range(n):
        v *= 1.0 + rng.gauss(mu, sigma)
        eq.append(v)
    return eq


def test_rendements_ignorent_les_prix_nuls():
    """Une division par zéro dans une courbe d'equity produirait un inf silencieux."""
    obtenu = sweep._rendements([100.0, 0.0, 50.0, 55.0])
    assert obtenu == pytest.approx([-1.0, 0.1], abs=1e-9)


def test_aucune_recommandation_sur_du_BRUIT_PUR(capsys):
    """Le test qui compte. Cinq courbes tirées de la MÊME loi : aucun ratio ne peut
    être meilleur. Le verdict doit refuser de conclure, malgré un « meilleur Sharpe »
    nécessairement non nul."""
    courbes = {c: _courbe(seed) for seed, c in
               enumerate((0.0, 0.25, 0.5, 0.75, 1.0))}
    meilleur = (1.0, {"sharpe": 1.23})
    sweep._verdict(courbes, meilleur, reference=0.5)
    sortie = capsys.readouterr().out
    assert "AUCUN ratio n'est distinguable" in sortie, sortie
    assert "bruit de sélection" in sortie


def test_le_seuil_de_detection_est_affiche(capsys):
    """À lire AVANT le tableau : si le seuil dépasse l'effet espéré, l'expérience ne
    peut pas conclure, et la lancer quand même produit du bruit qu'on lira comme un
    résultat."""
    courbes = {0.5: _courbe(1), 1.0: _courbe(2)}
    sweep._verdict(courbes, (1.0, {"sharpe": 1.0}), reference=0.5)
    sortie = capsys.readouterr().out
    assert "détectable" in sortie and "±" in sortie


def test_un_ecart_FRANC_est_bien_signale(capsys):
    """Contrepartie indispensable : l'instrument ne doit pas tout rejeter, sinon il ne
    mesure rien. Une dérive nettement supérieure doit ressortir."""
    courbes = {0.5: _courbe(1, mu=0.0002), 1.0: _courbe(1, mu=0.0016)}
    sweep._verdict(courbes, (1.0, {"sharpe": 2.0}), reference=0.5)
    sortie = capsys.readouterr().out
    assert "DISCERNABLE" in sortie, sortie
    assert "hors échantillon" in sortie, "un écart discernable reste à confirmer OOS"


def test_reference_absente_ne_casse_rien():
    """Part actuelle absente de la grille : se taire plutôt que planter."""
    sweep._verdict({0.25: _courbe(1)}, (0.25, {"sharpe": 1.0}), reference=0.5)


def test_la_comparaison_est_bien_APPARIEE():
    """Deux mélanges du même satellite sont très corrélés. La correction de
    Jobson-Korkie/Memmel exploite cette corrélation : ignorer l'appariement gonflerait
    l'erreur-type et rendrait le test aveugle."""
    a, b = _courbe(1), _courbe(1, mu=0.0009)
    d = comparer(sweep._rendements(a), sweep._rendements(b), periodes_par_an=252.0)
    assert d["disponible"] and d["correlation"] > 0.5, d
