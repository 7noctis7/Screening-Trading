"""Le seuil de détection ne dépend QUE du nombre d'années — pas de la fréquence.

Fausse piste fermée le 31/08, après l'avoir moi-même proposée : « raccourcis le pas de
rebalancement (21 → 5), tu auras plus d'observations et tu détecteras des effets plus
fins ». C'est faux deux fois.

1. Changer le pas change la STRATÉGIE — hebdomadaire au lieu de mensuel quadruple le
   turnover. On ne mesure plus la même chose.
2. Le seuil est INVARIANT à la fréquence : Z·sqrt(var·ppa) avec var ∝ 1/n et
   n = années × ppa → ppa s'annule.
"""

import pytest

from packages.research.sharpe_diff import seuil_detectable


def test_le_seuil_est_INVARIANT_a_la_frequence():
    """Le cœur du sujet : 11 ans en quotidien et en mensuel donnent le même seuil."""
    quotidien = seuil_detectable(11 * 252, 1.0, 0.99, 252.0)
    mensuel = seuil_detectable(11 * 12, 1.0, 0.99, 12.0)
    assert quotidien == pytest.approx(mensuel, abs=0.005), (quotidien, mensuel)


def test_seul_le_nombre_d_ANNEES_ameliore_le_seuil():
    s = [seuil_detectable(a * 252, 1.0, 0.99, 252.0) for a in (5, 11, 20, 40)]
    assert s == sorted(s, reverse=True), s
    assert s[0] > 2 * s[-1], "l'historique doit avoir un effet marqué"


def test_60_ans_seraient_necessaires_pour_le_seuil_du_gate():
    """Le gate promeut à +0,05. Ce chiffre n'est pas atteignable avec 11 ans, et ce
    n'est pas un défaut de mesure : c'est la quantité d'information disponible."""
    assert seuil_detectable(11 * 252, 1.0, 0.99, 252.0) > 0.05
    assert seuil_detectable(60 * 252, 1.0, 0.99, 252.0) < 0.06


def test_la_CORRELATION_est_le_vrai_levier():
    """À historique constant, resserrer le protocole (ne changer qu'une chose) fait
    plus que doubler la sensibilité."""
    large = seuil_detectable(11 * 252, 1.0, 0.95, 252.0)
    apparie = seuil_detectable(11 * 252, 1.0, 0.99, 252.0)
    assert apparie < large / 2, (apparie, large)


def test_le_diagnostic_du_labo_publie_les_deux_leviers(capsys):
    """Le message doit nommer ce qui marche, pas seulement ce qui ne marche pas."""
    from scripts.preset_lab import _pourquoi_echantillonner_plus_ne_sert_a_rien
    _pourquoi_echantillonner_plus_ne_sert_a_rien(12.0)
    sortie = capsys.readouterr().out
    assert "ANNÉES" in sortie and "CORRÉLATION" in sortie
    assert "RIEN" in sortie, "la fausse piste doit être nommée comme telle"
