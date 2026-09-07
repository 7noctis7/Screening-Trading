"""IC walk-forward du screening — on valide la MÉCANIQUE sur des séries construites.

Le mandat données-réelles s'applique à la production : ici, des séries synthétiques dont
on connaît la réponse sont le seul moyen de prouver que la mesure mesure la bonne chose.
"""
import numpy as np
import pytest

from packages.research.screening_ic import (
    N_DATES_MIN,
    _hors_echantillon,
    _rendement_futur,
    ic_a_la_date,
    mesurer,
)


class Bar:
    def __init__(self, close): self.close = close


class MoteurFactice:
    """Rend, pour chaque symbole, un score ÉGAL à son rendement futur (prescient) ou à
    du bruit, selon le mode. Permet de vérifier les deux bornes de la mesure."""

    class R:
        def __init__(self, symbol, score): self.symbol, self.score, self.passed = symbol, score, True

    def __init__(self, mode, horizon, graine=0):
        self.mode, self.horizon, self.rng = mode, horizon, np.random.default_rng(graine)

    def screen(self, panel, t=10**9, fundamentals=None, include_rejected=False):
        out = []
        for sym, bars in panel.items():
            if self.mode == "prescient":
                futur = _rendement_futur(bars, t, self.horizon)
                score = 0.0 if futur is None else futur
            else:
                score = float(self.rng.normal())
            out.append(self.R(sym, score))
        return out


def _panel(n_actifs=20, n_barres=1500, graine=0):
    rng = np.random.default_rng(graine)
    return {f"S{i}": [Bar(c) for c in 100 * np.cumprod(1 + rng.normal(0, 0.012, n_barres))]
            for i in range(n_actifs)}


def test_rendement_futur_deborde_rend_none():
    bars = [Bar(10.0), Bar(11.0), Bar(12.0)]
    assert _rendement_futur(bars, 0, 2) == pytest.approx(0.2)
    assert _rendement_futur(bars, 2, 1) is None      # la fenêtre sort de l'historique


def test_un_score_prescient_donne_un_ic_de_un():
    """Borne HAUTE : si le score EST le rendement futur, l'IC de rang vaut 1."""
    panel = _panel()
    ic = ic_a_la_date(panel, MoteurFactice("prescient", 21), t=300, horizon=21)
    assert ic is not None and ic > 0.99


def test_un_score_aleatoire_donne_un_ic_nul_en_moyenne():
    """Borne BASSE : du bruit ne prédit rien. C'est le cas à distinguer d'un vrai edge."""
    panel = _panel(n_actifs=40, n_barres=3000, graine=1)
    res = mesurer(panel, MoteurFactice("bruit", 21, graine=2), horizon=21)
    assert res["available"] is True
    assert abs(res["ic_moyen"]) < 0.1
    assert res["t_stat"] is None or abs(res["t_stat"]) < 3.0


def test_le_pas_egale_l_horizon_par_defaut():
    """Des fenêtres qui se chevauchent partagent des rendements : t-stat gonflé pour rien."""
    panel = _panel(n_barres=1200)
    res = mesurer(panel, MoteurFactice("bruit", 21), horizon=21)
    assert res["pas"] == 21 and res["chevauchement"] is False


def test_historique_trop_court_est_uncalibrated_pas_un_chiffre():
    panel = _panel(n_actifs=10, n_barres=400)
    res = mesurer(panel, MoteurFactice("bruit", 21), horizon=21)
    assert res["available"] is False and res["status"] == "UNCALIBRATED"
    assert res["n_dates"] < N_DATES_MIN


def test_coupe_hors_echantillon_est_chronologique():
    """Un signal qui s'éteint dans la seconde moitié n'est PAS robuste."""
    ics = [0.30] * 10 + [0.00] * 10
    res = _hors_echantillon(list(range(20)), ics)
    assert res["ic_premiere_moitie"] == pytest.approx(0.30)
    assert res["ic_seconde_moitie"] == pytest.approx(0.0)
    assert res["robuste"] is False


def test_signal_stable_est_declare_robuste():
    ics = [0.06, 0.05, 0.07, 0.04, 0.06, 0.05] * 2
    res = _hors_echantillon(list(range(12)), ics)
    assert res["ratio_oos"] is not None and res["robuste"] is True


def test_trop_peu_de_dates_pour_couper_n_est_jamais_robuste():
    res = _hors_echantillon([0, 1, 2, 3], [0.5, 0.5, 0.5, 0.5])
    assert res["ratio_oos"] is None and res["robuste"] is False
