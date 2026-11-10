"""Banc du classement candidat : il voit un signal planté, pas un signal absent, et ne lit
jamais le futur. Séries SYNTHÉTIQUES : la mécanique, jamais un chiffre de marché."""
from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from packages.core.models import Bar
from packages.research.labo_classement import (
    classement_momentum,
    classement_placebo,
    classement_residuel,
    ecart_apparie,
    lignes,
    panneau,
    sur_coupe_commune,
)
from packages.research.portefeuille_classement import (
    decisions,
    episodes,
    simuler,
    statistiques_episodes,
)

N, JOURS, EST, FORM, SAUT = 40, 1300, 504, 252, 21


def _donnees(graine: int, derive_propre: float) -> dict:
    """40 titres = bêta × marché + bruit ; `derive_propre` plante une dérive propre qui
    CHANGE par périodes d'environ un an (phase tirée par titre).

    Par périodes et non constante : le score retire la moyenne propre du titre sur la
    fenêtre d'estimation. Une dérive permanente est donc invisible PAR DÉFINITION — le
    signal publié est « le titre fait mieux que sa propre habitude », pas « le titre monte »."""
    rng = np.random.default_rng(graine)
    marche = rng.normal(0.0003, 0.01, JOURS)
    blocs = (np.arange(JOURS)[:, None] + rng.integers(0, 250, N)[None, :]) // 250
    regimes = rng.normal(0, 1, (blocs.max() + 1, N))[blocs, np.arange(N)[None, :]]
    R = (np.outer(marche, rng.uniform(0.5, 1.5, N)) + rng.normal(0, 0.012, (JOURS, N))
         + derive_propre * regimes)
    closes = 100.0 * np.cumprod(1.0 + R, axis=0)
    t0 = datetime(2018, 1, 1, tzinfo=timezone.utc)
    return {f"S{k:02d}": [Bar(f"S{k:02d}", "1d", t0 + timedelta(days=i), c, c, c, c, 1e6)
                          for i, c in enumerate(closes[:, k])] for k in range(N)}


CANDIDAT = classement_residuel(EST, FORM, SAUT, True)


def test_le_panneau_est_aligne_par_date_et_le_premier_jour_n_a_pas_de_rendement():
    pan = panneau(_donnees(0, 0.0))
    assert pan["C"].shape == pan["R"].shape == (JOURS, N)
    assert np.isnan(pan["R"][0]).all() and np.isfinite(pan["R"][1:]).all()


def test_un_signal_plante_est_vu():
    pan = panneau(_donnees(1, 0.0015))
    li, compteurs = lignes(pan, CANDIDAT, h=5, pas=5, debut=EST)
    ic = np.array([x["ic"] for x in li])
    assert compteurs["dates_mesurees"] == len(li) >= 50
    assert ic.mean() > 0.05 and ic.mean() / ic.std(ddof=1) * np.sqrt(ic.size) > 3


def test_sur_du_bruit_rien_n_est_vu():
    pan = panneau(_donnees(2, 0.0))
    li, _ = lignes(pan, CANDIDAT, h=5, pas=5, debut=EST)
    ic = np.array([x["ic"] for x in li])
    assert abs(ic.mean() / ic.std(ddof=1) * np.sqrt(ic.size)) < 3


def test_le_score_du_jour_t_ignore_tout_ce_qui_suit():
    """ANTI-LOOKAHEAD : réécrire les clôtures après t ne change ni le candidat ni le témoin."""
    data = _donnees(3, 0.001)
    pan = panneau(data)
    t = 700
    futur = {s: [b if i <= t else Bar(b.instrument, b.timeframe, b.ts, 1, 1, 1, 1.0, 1e6)
                 for i, b in enumerate(barres)] for s, barres in data.items()}
    pan_futur = panneau(futur)
    for classement in (CANDIDAT, classement_momentum(252, 21)):
        assert np.array_equal(classement(pan, t), classement(pan_futur, t), equal_nan=True)


def test_la_cible_part_du_prix_d_execution_pas_du_close_du_signal():
    """Un bond du titre le lendemain de la décision (close t → close t + 1) ne doit PAS
    être compté : la position n'est prise qu'au close de t + 1."""
    data = _donnees(4, 0.0)
    pan = panneau(data)
    t, col = 600, 0
    avant, _ = lignes(pan, classement_momentum(252, 21), h=5, pas=5, debut=t)
    pan["C"][t + 1:, col] *= 3.0                      # ×3 dès t + 1, maintenu ensuite
    apres, _ = lignes(pan, classement_momentum(252, 21), h=5, pas=5, debut=t)
    assert avant[0]["ic"] == pytest.approx(apres[0]["ic"])


def test_l_ecart_apparie_distingue_le_candidat_du_temoin_ou_dit_uncalibrated():
    pan = panneau(_donnees(5, 0.0015))
    cand, _ = lignes(pan, CANDIDAT, 5, 5, EST)
    bruit, _ = lignes(pan, classement_placebo(CANDIDAT, 7), 5, 5, EST)
    e = ecart_apparie(cand, bruit, n_nulles=500)
    assert e["available"] and e["ecart_ic_moyen"] > 0 and e["p_signes"] < 0.05
    assert ecart_apparie(cand[:5], bruit[:5])["status"] == "UNCALIBRATED"


def test_le_placebo_garde_la_coupe_et_perd_l_information():
    pan = panneau(_donnees(6, 0.0015))
    sc, pl = CANDIDAT(pan, 700), classement_placebo(CANDIDAT, 1)(pan, 700)
    assert np.array_equal(np.isfinite(sc), np.isfinite(pl))
    assert sorted(sc[np.isfinite(sc)]) == sorted(pl[np.isfinite(pl)])
    assert not np.array_equal(sc, pl)


def test_le_portefeuille_paie_sa_rotation_et_rien_d_autre():
    pan = panneau(_donnees(7, 0.001))
    decs, _ = decisions(pan, CANDIDAT, pas=5, debut=EST, top_k=12)
    brut = simuler(pan, decs, "cols", 0.0)
    net = simuler(pan, decs, "cols", 0.0005)
    attendu = 0.0005 * sum(net["rotations"])
    assert net["rotations"][0] == pytest.approx(1.0)          # premier achat : tout
    assert (brut["r"].sum() - net["r"].sum()) == pytest.approx(attendu, rel=1e-9)
    assert net["barres_manquantes"] == net["ordres_non_executables"] == 0


def test_un_titre_sans_cloture_a_l_execution_reste_en_especes():
    pan = panneau(_donnees(8, 0.001))
    decs, _ = decisions(pan, CANDIDAT, pas=5, debut=EST, top_k=12)
    pan["C"][decs[0]["e"], int(decs[0]["cols"][0])] = np.nan
    s = simuler(pan, decs[:1], "cols", 0.0)
    assert s["ordres_non_executables"] == 1 and s["rotations"][0] == pytest.approx(11 / 12)


def test_les_episodes_sont_nets_de_deux_cotes_et_comptes():
    pan = panneau(_donnees(9, 0.0015))
    decs, _ = decisions(pan, CANDIDAT, pas=5, debut=EST, top_k=12)
    bruts, c = episodes(pan, decs, 0.0)
    nets, _ = episodes(pan, decs, 0.001)
    assert c["episodes_clos"] == len(bruts) > 30 and c["episodes_ouverts"] == 12
    assert np.allclose(np.array(bruts) - np.array(nets), 0.002)
    st = statistiques_episodes(nets)
    assert st["available"] and 0 < st["taux_gain"] < 1 and st["profit_factor"] > 0
    assert st["ic95"][0] <= st["esperance_simple"] <= st["ic95"][1]


def test_l_ecart_apparie_porte_sur_les_memes_titres_des_deux_cotes():
    """Un titre que le candidat ne peut pas classer (trou dans ses 36 mois) est classé
    par le témoin : sans coupe commune, les deux IC portent sur des ensembles différents."""
    pan = panneau(_donnees(10, 0.001))
    pan["R"][300, :5] = np.nan                       # 5 titres : fenêtre du candidat trouée
    pan["C"][300, :5] = np.nan
    temoin, t = classement_momentum(252, 21), 700
    assert np.isfinite(temoin(pan, t)).sum() == np.isfinite(CANDIDAT(pan, t)).sum() + 5
    a = sur_coupe_commune(CANDIDAT, temoin)(pan, t)
    b = sur_coupe_commune(temoin, CANDIDAT)(pan, t)
    assert np.array_equal(np.isfinite(a), np.isfinite(b))
    la, _ = lignes(pan, sur_coupe_commune(CANDIDAT, temoin), 5, 5, EST)
    lb, _ = lignes(pan, sur_coupe_commune(temoin, CANDIDAT), 5, 5, EST)
    assert [x["n"] for x in la] == [x["n"] for x in lb]
