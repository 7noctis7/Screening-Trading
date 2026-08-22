"""Un versement n'est pas une performance.

Ces tests figent le comportement attendu d'un compte réel : la mesure doit être INSENSIBLE au
montant et à la date des mouvements de trésorerie, et refuser de deviner quand elle ne sait pas.
"""
import math

from packages.portfolio.twr import detect_flows, flow_report, robust_sigma, twr


def _marche(n=60, r=0.001, vol=0.01, seed=7):
    """Série de marché douce et déterministe (pas d'aléa non contrôlé)."""
    v, out = 10_000.0, [10_000.0]
    for i in range(n):
        v *= 1.0 + r + vol * math.sin(seed * (i + 1))
        out.append(v)
    return out


def test_sans_mouvement_le_twr_egale_la_variation_brute():
    s = _marche()
    res = twr(s)
    assert res["available"] and res["n_flows"] == 0
    assert abs(res["total_return"] - res["raw_return"]) < 1e-9


def test_un_depot_ne_cree_pas_de_performance():
    s = _marche()
    ref = twr(s)["total_return"]
    # Dépôt de 50 000 $ au milieu : la valeur du compte sextuple, la GESTION n'a rien fait.
    i = 30
    avec = s[:i] + [v + 50_000.0 for v in s[i:]]
    res = twr(avec)
    assert res["n_flows"] == 1, res["flows"]
    # Le rendement brut explose ; le TWR reste de l'ordre du rendement de gestion.
    assert res["raw_return"] > 4.0
    assert abs(res["total_return"] - ref) < 0.05


def test_un_retrait_ne_cree_pas_de_perte():
    s = _marche()
    i = 40
    avec = s[:i] + [v * 0.25 for v in s[i:]]      # retrait des trois quarts
    res = twr(avec)
    assert res["n_flows"] == 1
    assert res["raw_return"] < -0.5               # le compte a fondu…
    assert res["total_return"] > 0                # …mais la gestion était gagnante


def test_le_drawdown_du_retrait_disparait_des_sous_periodes():
    """Le maxDD de -22,8 % observé venait d'un mouvement, pas du marché."""
    s = _marche()
    avec = s[:40] + [v * 0.25 for v in s[40:]]
    pire = min(twr(avec)["returns"])
    assert pire > -0.10, f"une baisse de {pire:.1%} subsiste : le mouvement n'a pas été neutralisé"


def test_la_date_du_versement_ne_change_pas_le_resultat():
    """Propriété qui DÉFINIT le rendement pondéré dans le temps."""
    s = _marche()
    r20 = twr(s[:20] + [v + 50_000.0 for v in s[20:]])["total_return"]
    r45 = twr(s[:45] + [v + 50_000.0 for v in s[45:]])["total_return"]
    assert abs(r20 - r45) < 0.05


def test_une_vraie_journee_de_marche_nest_pas_confisquee():
    """−8 % de krach reste de la performance : le seuil ne doit pas manger le marché."""
    s = _marche(vol=0.02)
    s = s[:30] + [v * 0.92 for v in s[30:]]
    res = twr(s)
    assert res["n_flows"] == 0, "une séance de marché a été prise pour un virement"


def test_serie_trop_courte_ne_devine_rien():
    assert detect_flows([100.0, 120.0, 90.0]) == []


def test_serie_plate_ne_devine_rien():
    """Dispersion nulle → aucun seuil calculable → on ne détecte pas au hasard."""
    assert robust_sigma([0.0] * 40) == 0.0
    assert detect_flows([100.0] * 40) == []


def test_valeurs_non_positives_rompent_la_chaine_sans_planter():
    s = [100.0, 110.0, 0.0, 120.0, 130.0] + [130.0 + i for i in range(40)]
    res = twr(s)
    assert res["available"]
    assert all(x == x for x in res["returns"])


def test_le_rapport_nomme_les_mouvements():
    s = _marche()
    avec = s[:30] + [v + 50_000.0 for v in s[30:]]
    dates = [f"2026-06-{d:02d}" for d in range(1, len(avec) + 1)]
    rep = flow_report(avec, dates=dates)
    assert rep["contamine"] and rep["n_flows"] == 1
    m = rep["mouvements"][0]
    assert m["montant"] > 45_000
    assert m["sigmas"] > 5
    assert m["date"] is not None
    assert "neutralis" in rep["note"]


def test_rapport_sans_mouvement_le_dit():
    rep = flow_report(_marche())
    assert rep["available"] and not rep["contamine"] and rep["n_flows"] == 0
    assert "Aucun mouvement" in rep["note"]
