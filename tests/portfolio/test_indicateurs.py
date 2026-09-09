"""Ratios d'allocation — tous des CONSTATS, aucun n'est une prévision."""
import numpy as np
import pytest

from packages.portfolio.indicateurs import (
    bornes_52_semaines,
    correlation_moyenne,
    performance_realisee,
    positions_effectives,
    ratio_diversification,
)


def _cov(vols, correlation=0.0):
    sig = np.asarray(vols, dtype=float)
    corr = np.full((len(sig), len(sig)), correlation)
    np.fill_diagonal(corr, 1.0)
    return corr * np.outer(sig, sig)


def test_diversification_vaut_UN_quand_tout_bouge_ensemble():
    """C'est le point du ratio : dix lignes parfaitement corrélées n'en valent qu'une."""
    ratio = ratio_diversification([1 / 3] * 3, _cov([0.2, 0.3, 0.25], correlation=0.999))
    assert 1.0 <= ratio < 1.02


def test_diversification_croit_quand_la_correlation_baisse():
    faible = ratio_diversification([1 / 3] * 3, _cov([0.2, 0.2, 0.2], correlation=0.8))
    forte = ratio_diversification([1 / 3] * 3, _cov([0.2, 0.2, 0.2], correlation=0.0))
    assert forte > faible > 1.0


def test_positions_effectives_corrige_la_concentration():
    """14 lignes dont une à 38 % ne valent PAS 14 lignes — c'est ce que le nombre dit."""
    assert positions_effectives([1 / 14] * 14) == pytest.approx(14.0)
    concentre = positions_effectives([0.38] + [0.62 / 13] * 13)
    assert 5.0 < concentre < 7.0


def test_une_seule_ligne_donne_une_position_effective():
    assert positions_effectives([1.0]) == pytest.approx(1.0)


def test_correlation_moyenne_ignore_la_diagonale():
    """Inclure les 1,0 de la diagonale gonflerait mécaniquement la moyenne."""
    assert correlation_moyenne(_cov([0.2, 0.2, 0.2], correlation=0.4)) == pytest.approx(0.4)


def test_bornes_52_semaines_et_asymetrie_du_retour():
    bornes = bornes_52_semaines({"2026-01-01": 100.0, "2026-06-01": 150.0, "2026-09-01": 120.0})
    assert bornes["haut_52s"] == 150.0 and bornes["bas_52s"] == 100.0
    assert bornes["distance_haut"] == pytest.approx(-0.2)
    assert bornes["position_dans_bande"] == pytest.approx(0.4)


def test_bornes_sur_une_serie_vide_ne_rendent_pas_zero():
    """Zéro serait un prix. L'absence doit rester None."""
    for valeur in bornes_52_semaines({}).values():
        assert valeur is None


def test_la_fenetre_est_bornee_aux_252_derniers_jours():
    """Un plus-haut de 2019 n'est pas un plus-haut 52 semaines."""
    serie = {f"2024-01-{d:02d}": 500.0 for d in range(1, 10)}      # très ancien, très haut
    serie |= {f"2026-0{m}-01": 100.0 for m in range(1, 10)}
    bornes = bornes_52_semaines(serie, jours=9)
    assert bornes["haut_52s"] == 100.0


def test_performance_realisee_porte_son_avertissement():
    """Le chiffre est biaisé vers le haut par construction : l'allocation connaissait ces
    prix. L'avertissement doit voyager AVEC la valeur, jamais dans un commentaire."""
    rng = np.random.default_rng(0)
    dates = [f"2026-{1 + i // 28:02d}-{1 + i % 28:02d}" for i in range(60)]
    series = {s: dict(zip(dates, 100 * np.cumprod(1 + rng.normal(0.001, 0.01, 60))))
              for s in ("A", "B")}
    out = performance_realisee(series, ["A", "B"], [0.5, 0.5])
    assert out["sharpe_realise"] is not None
    assert "rétrospectif" in out["avertissement"]


def test_trop_peu_d_observations_ne_produit_aucun_sharpe():
    series = {"A": {"2026-01-01": 1.0, "2026-01-02": 1.1}}
    out = performance_realisee(series, ["A"], [1.0])
    assert out["sharpe_realise"] is None and out["rendement_annualise"] is None


def test_les_positions_effectives_ne_depassent_JAMAIS_le_nombre_de_lignes():
    """Mesuré le 07/09 : « 25,6 positions effectives » affiché pour 14 actifs. Le budget de
    perte avait ramené l'exposition à 47,3 %, les poids ne sommaient plus à 1, et 1/Σw²
    gonflait mécaniquement. La mesure porte sur la RÉPARTITION, pas sur la somme."""
    for n in (3, 14, 40):
        for exposition in (1.0, 0.473, 0.05):
            poids = [exposition / n] * n
            assert positions_effectives(poids) == pytest.approx(float(n)), (n, exposition)


def test_la_concentration_est_lue_a_exposition_reduite_comme_a_pleine():
    """Une ligne à 38 % du RISQUE reste une ligne à 38 %, qu'on soit investi à 100 % ou 50 %."""
    plein = positions_effectives([0.38] + [0.62 / 13] * 13)
    reduit = positions_effectives([0.5 * 0.38] + [0.5 * 0.62 / 13] * 13)
    assert plein == pytest.approx(reduit)


def test_un_portefeuille_entierement_en_cash_ne_rend_pas_un_nombre():
    assert positions_effectives([0.0, 0.0, 0.0]) is None
