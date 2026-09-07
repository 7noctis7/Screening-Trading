"""Les quatre synergies inter-onglets — chacune doit RESTER inoffensive sans preuve."""
import numpy as np
import pytest

from packages.portfolio.conviction import somers_d, vues_combinees
from packages.portfolio.recommendation import chemin_de_moindre_effort, moderation_regime

IC_SOLIDE = {"t_stat": 4.0, "n_dates": 200}


# --- Régime macro : exposition seulement, et seulement vers le bas ------------------------

def test_sans_regime_aucune_moderation():
    assert moderation_regime(None, None)["facteur"] == 1.0


def test_regime_defensif_sans_preuve_ne_fait_RIEN():
    """Le câblage est actif et sans effet tant que rien n'est démontré. C'est voulu."""
    out = moderation_regime({"cycle": "contraction", "risk_mode": "risk-off"}, None)
    assert out["facteur"] == 1.0 and out["reduction"] == 0.0
    assert "non mesurée" in out["motif"]


def test_regime_defensif_avec_preuve_reduit_l_exposition():
    out = moderation_regime({"cycle": "contraction", "risk_mode": "risk-off"}, IC_SOLIDE)
    assert 0.0 < out["reduction"] <= 0.05          # borné par AMPLITUDE_MAX
    assert out["facteur"] == pytest.approx(1.0 - out["reduction"])


def test_un_regime_favorable_n_augmente_JAMAIS_l_exposition():
    """Asymétrie assumée : se tromper en étant prudent coûte un rendement manqué ; se
    tromper en étant agressif peut coûter la capacité à rester investi."""
    out = moderation_regime({"cycle": "expansion", "risk_mode": "risk-on"}, IC_SOLIDE)
    assert out["facteur"] == 1.0 and out["reduction"] == 0.0


def test_la_moderation_ne_depasse_jamais_l_amplitude_max():
    from packages.profile.tilts import AMPLITUDE_MAX
    fort = moderation_regime({"cycle": "recession", "risk_mode": "risk-off"},
                             {"t_stat": 99.0, "n_dates": 10000})
    assert fort["reduction"] <= AMPLITUDE_MAX + 1e-12


# --- Chemin de moindre effort ------------------------------------------------------------

def _cov(vols):
    return np.diag(np.asarray(vols, dtype=float) ** 2)


def test_le_premier_mouvement_est_celui_qui_evite_le_plus_de_risque():
    cov = _cov([0.60, 0.25, 0.20, 0.10])
    syms = ["VOLATIL", "MOYEN", "CALME", "TRES_CALME"]
    etapes = chemin_de_moindre_effort(cov, syms, {"VOLATIL": 0.5, "MOYEN": 0.5},
                                      {"CALME": 0.5, "TRES_CALME": 0.5})
    assert etapes[0]["symbol"] == "VOLATIL"
    assert etapes[0]["part_du_gain"] > 0.9          # l'essentiel dès le 1er mouvement
    assert etapes[0]["turnover_cumule"] < 0.3       # pour moins d'un tiers du turnover


def test_le_turnover_cumule_croit_et_finit_a_la_cible():
    cov = _cov([0.3, 0.2, 0.1])
    syms = ["A", "B", "C"]
    etapes = chemin_de_moindre_effort(cov, syms, {"A": 0.6, "B": 0.4}, {"B": 0.5, "C": 0.5})
    tours = [e["turnover_cumule"] for e in etapes]
    assert tours == sorted(tours)
    assert etapes[-1]["part_du_gain"] == pytest.approx(1.0, abs=1e-6)


def test_aucun_mouvement_quand_on_est_deja_a_la_cible():
    cov = _cov([0.3, 0.2])
    assert chemin_de_moindre_effort(cov, ["A", "B"], {"A": 0.5, "B": 0.5},
                                    {"A": 0.5, "B": 0.5}) == []


# --- ML dans les vues : pondéré par sa force, donc quasi inoffensif ----------------------

def test_auc_devient_un_ic_comparable():
    """AUC 0,52 « edge détecté » = IC 0,04. Le chiffre brut cache cette petitesse."""
    assert somers_d(0.52) == pytest.approx(0.04)
    assert somers_d(0.50) == pytest.approx(0.0)
    assert somers_d(None) is None


def test_sans_ml_on_retombe_exactement_sur_le_score_seul():
    z_seul, ic_seul = vues_combinees([2.0, 1.0, 0.0, -1.0], None, 0.06, None)
    z_nul, ic_nul = vues_combinees([2.0, 1.0, 0.0, -1.0], [1.0, 2.0, 3.0, 4.0], 0.06, 0.0)
    assert np.allclose(z_seul, z_nul) and ic_seul == ic_nul == 0.06


def test_un_ml_faible_deplace_peu_la_combinaison():
    """IC 0,04 contre 0,06 : le ML pèse, sans dominer — et l'IC combiné reste modeste."""
    z, ic = vues_combinees([2.0, 1.0, 0.0, -1.0], [0.0, 0.0, 1.0, 2.0], 0.06, somers_d(0.52))
    assert ic == pytest.approx(np.hypot(0.06, 0.04), rel=1e-6)
    assert z[0] > z[-1]                    # l'ordre du score domine encore


def test_l_ic_combine_ne_depasse_jamais_la_somme_des_deux():
    """Deux signaux corrélés font MOINS que la racine des carrés : on borne par la somme."""
    _, ic = vues_combinees([1.0, 2.0], [1.0, 2.0], 0.30, 0.30)
    assert ic <= 0.60 + 1e-12
