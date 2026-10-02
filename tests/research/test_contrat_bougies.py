"""Le contrat +4 % / rapport > 3 est une définition, pas un résultat."""

from pathlib import Path

import numpy as np

from packages.research.contrat_bougies import (
    FENETRE, GAIN, HORIZON, STOP, bilan, construire, decision, derniere_connue,
    esperance, issue, ligne, rapport, resultat_net, seuil_brut,
)
from packages.research.frequence_bougies import juger


def _serie(n, close, high=None, low=None):
    c = np.full(n, close, float)
    h = np.full(n, close + 0.1, float) if high is None else np.asarray(high, float)
    lo = np.full(n, close - 0.1, float) if low is None else np.asarray(low, float)
    v = np.ones(n)
    return c, h, lo, v


def test_on_ne_joue_que_les_coups_dont_l_esperance_est_positive():
    assert esperance(0.20) < 0
    assert esperance(0.40) > 0
    assert abs(esperance(seuil_brut())) < 1e-9
    livre = bilan([0.10, 0.10, 0.90], [0, 0, 1], calibre=True)
    assert livre["n_pris"] == 1
    assert livre["esperance_des_coups_pris"] == resultat_net(True)
    assert livre["esperance_par_occasion"] > livre["esperance_tout_prendre"]
    assert 0 < livre["mise"] <= 0.05
    rien = bilan([0.90], [1], calibre=False)
    assert rien["n_pris"] == 0 and rien["mise"] == 0.0
    assert rien["esperance_par_occasion"] == 0.0
    assert rapport() == GAIN / STOP
    assert rapport() > 3
    assert abs(seuil_brut() - (STOP + 0.001) / (GAIN + STOP)) < 1e-12
    assert decision(0.99, calibre=False) == "abstention"
    assert decision(0.01, calibre=True) == "abstention"
    assert decision(0.99, calibre=True) == "candidat"


def test_plus_4pct_avant_le_stop_est_un_succes_et_l_ambigu_est_ecarte():
    n = 30
    c, h, lo, _ = _serie(n, 100.0)
    h[5] = 104.01
    assert issue(h, lo, c, 4) == 1
    c2, h2, lo2, _ = _serie(n, 100.0)
    lo2[6] = 98.75
    assert issue(h2, lo2, c2, 4) == 0
    h3 = h.copy()
    lo3 = lo.copy()
    h3[5] = 105.0
    lo3[5] = 98.0
    assert issue(h3, lo3, c, 4) is None
    assert issue(h, lo, c, n - 2) is None


def test_une_publication_future_ou_du_jour_ne_rentre_pas():
    pubs = [("2026-01-10", 0.5), ("2026-02-01", 9.0)]
    assert derniere_connue(pubs, "2026-01-10") == (0.0, 0.0)
    assert derniere_connue(pubs, "2026-01-11") == (0.5, 1.0)
    assert derniere_connue([], "2026-06-01") == (0.0, 0.0)


def test_les_features_ne_lisent_pas_la_bougie_suivante():
    n = 40
    c, h, lo, v = _serie(n, 100.0)
    c[21] = 110.0
    dates = [f"2024-01-{i+1:02d}" for i in range(n)]
    pubs = [("2024-01-01", 0.2)]
    fonds = [("2023-12-01", 7.0)]
    avant = ligne(c, h, lo, v, 20, dates[20], pubs, fonds)
    c[21] = 1.0
    h[21] = 1.0
    lo[21] = 1.0
    apres = ligne(c, h, lo, v, 20, dates[20], pubs, fonds)
    assert avant is not None and avant == apres
    assert avant[7] == 0.2 and avant[8] == 1.0
    assert avant[9] == 7.0 and avant[10] == 1.0
    assert len(avant) == 11


def test_construire_aligne_etiquette_et_features_sans_fuite():
    n = FENETRE + HORIZON + 5
    c, h, lo, v = _serie(n, 100.0)
    h[FENETRE + 1] = 104.01
    dates = [f"2024-06-{i+1:02d}" for i in range(n)]
    X, y = construire(c, h, lo, v, dates, [("2024-06-01", 0.3)], [("2024-05-01", 4.0)])
    assert X.shape[1] == 11
    assert set(y.tolist()) <= {0, 1}
    assert 1 in y.tolist()


def test_sans_assez_de_lignes_aucune_probabilite_n_est_publiee():
    X = np.zeros((10, 11))
    y = np.array([0, 1] * 5)
    out = juger(X, y)
    assert out["calibre"] is False and out["decision"] == "abstention"


def test_le_yaml_fige_les_memes_nombres_que_le_code():
    texte = Path("config/essais/2026-10-02_bougies_4pct.yaml").read_text()
    assert "gain: 0.04" in texte and "stop: 0.0125" in texte
    assert "fenetre_bougies: 20" in texte and "ordres: aucun" in texte
