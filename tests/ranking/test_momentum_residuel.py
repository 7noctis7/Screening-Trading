"""Momentum résiduel : causal, neutre au marché, et verrouillé contre sa dégénérescence.

Séries SYNTHÉTIQUES : on valide la mécanique et la causalité, jamais un chiffre de marché.
"""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pytest

from packages.core.models import Bar
from packages.ranking import factor_calcs
from packages.ranking.factors import FactorContext
from packages.ranking.momentum_residuel import (
    ESTIMATION,
    FORMATION,
    SAUT,
    STATUT,
    rendements_marche,
    scores_residuels,
    verifier_fenetres,
)

N_TITRES = 30


def _marche_et_titres(graine: int = 0, n_jours: int = ESTIMATION):
    """(R, m) : 30 titres = bêta × marché + bruit propre, sans aucun signal planté."""
    rng = np.random.default_rng(graine)
    marche = rng.normal(0.0004, 0.01, n_jours)
    betas = rng.uniform(0.5, 1.5, N_TITRES)
    R = np.outer(marche, betas) + rng.normal(0.0, 0.012, (n_jours, N_TITRES))
    return R, rendements_marche(R)


def test_le_score_ne_lit_rien_apres_le_jour_de_decision():
    """ANTI-LOOKAHEAD. Le score du jour t ne change pas quand on réécrit tout l'après-t."""
    rng = np.random.default_rng(1)
    R, _ = _marche_et_titres(n_jours=ESTIMATION + 60)
    t = ESTIMATION                                   # la fenêtre se termine à l'index t − 1
    avant = scores_residuels(R[:t], rendements_marche(R[:t]))
    futur = R.copy()
    futur[t:] = rng.normal(0.05, 0.2, futur[t:].shape)     # un futur absurde
    apres = scores_residuels(futur[:t], rendements_marche(futur[:t]))
    assert np.array_equal(avant, apres)


def test_une_exposition_au_marche_ne_donne_aucun_score():
    """Ajouter 0,7 × marché à un titre change son momentum de prix, pas son score."""
    R, m = _marche_et_titres()
    base = scores_residuels(R, m)
    charge = R.copy()
    charge[:, 0] += 0.7 * m
    assert scores_residuels(charge, m)[0] == pytest.approx(base[0], abs=1e-9)


def test_un_titre_porte_par_le_marche_ne_passe_pas_devant_un_titre_porte_par_lui_meme():
    """Le cœur de la thèse. Marché en forte hausse : le titre à bêta 2 a le meilleur
    momentum de PRIX ; le titre à dérive propre a le meilleur score résiduel."""
    R, m = _marche_et_titres()
    m = m + 0.002                                   # marché en hausse sur toute la fenêtre
    formation = slice(ESTIMATION - FORMATION, ESTIMATION - SAUT)
    beta_haut = 2.0 * m                             # aucun mouvement propre
    propre = 0.5 * m
    propre[formation] += 0.0015                     # dérive propre pendant la formation
    R[:, 0], R[:, 1] = beta_haut, propre
    prix = (1 + R[formation]).prod(axis=0)
    assert prix[0] > prix[1]                        # le momentum classique préfère le bêta
    s = scores_residuels(R, m)
    assert s[1] > s[0]
    assert s[1] == np.nanmax(s)


def test_la_fenetre_d_estimation_egale_a_la_formation_est_refusee():
    """Avec une constante, les résidus somment à zéro : le score deviendrait l'opposé du
    dernier mois, un retournement vendu sous le nom de momentum."""
    with pytest.raises(ValueError, match="retournement"):
        verifier_fenetres(FORMATION, FORMATION, SAUT)
    R, m = _marche_et_titres(n_jours=FORMATION)
    with pytest.raises(ValueError):
        scores_residuels(R, m)


def test_un_trou_dans_l_historique_ne_se_comble_pas():
    R, m = _marche_et_titres()
    R[100, 3] = np.nan
    s = scores_residuels(R, rendements_marche(R))
    assert np.isnan(s[3]) and np.isfinite(np.delete(s, 3)).all()


def test_sans_marche_mesurable_aucun_titre_n_est_classe():
    """Moins de 20 titres cotés un jour : la moyenne n'est pas un marché, on ne classe pas."""
    R, _ = _marche_et_titres()
    etroit = R[:, :10]
    assert np.isnan(rendements_marche(etroit)).all()
    assert np.isnan(scores_residuels(etroit, rendements_marche(etroit))).all()


def _panel(R: np.ndarray) -> dict[str, list[Bar]]:
    t0 = datetime(2015, 1, 1, tzinfo=timezone.utc)
    closes = 100.0 * np.cumprod(1.0 + np.vstack([np.zeros(R.shape[1]), R]), axis=0)
    return {f"S{k:02d}": [Bar(f"S{k:02d}", "1d", t0 + timedelta(days=i), c, c, c, c, 1e6)
                          for i, c in enumerate(closes[:, k])]
            for k in range(R.shape[1])}


def test_le_plugin_est_enregistre_et_classe_comme_la_fonction_pure():
    R, m = _marche_et_titres()
    facteur = factor_calcs.create("residual_momentum")
    valeurs = facteur.values(FactorContext(panel=_panel(R), t=ESTIMATION))
    attendu = scores_residuels(R, m)
    obtenu = np.array([valeurs[f"S{k:02d}"] for k in range(N_TITRES)])
    assert obtenu == pytest.approx(attendu, abs=1e-6)


def test_le_plugin_ignore_les_barres_posterieures_a_t():
    """ANTI-LOOKAHEAD côté registre : des barres après `ctx.t` ne changent rien."""
    R, _ = _marche_et_titres(n_jours=ESTIMATION + 40)
    panel = _panel(R)
    facteur = factor_calcs.create("residual_momentum")
    avant = facteur.values(FactorContext(panel=panel, t=ESTIMATION))
    for barres in panel.values():
        for i in range(ESTIMATION + 1, len(barres)):
            barres[i] = replace(barres[i], open=1.0, high=1.0, low=1.0, close=1.0)
    assert facteur.values(FactorContext(panel=panel, t=ESTIMATION)) == avant


def test_historique_trop_court_rien_n_est_invente():
    R, _ = _marche_et_titres(n_jours=300)
    valeurs = factor_calcs.create("residual_momentum").values(
        FactorContext(panel=_panel(R), t=300))
    assert all(np.isnan(v) for v in valeurs.values())


def test_le_candidat_n_est_dans_aucun_classement_de_production():
    """CANDIDATE : enregistré, mais sans poids dans `config/factors.yaml`."""
    assert STATUT == "CANDIDATE_UNCALIBRATED"
    config = (Path(__file__).resolve().parents[2] / "config" / "factors.yaml").read_text()
    assert "residual_momentum" not in config
