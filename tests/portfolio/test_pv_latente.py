"""Le tableau de bord montre la PV du jour ; il ne montre pas le chemin.

Une ligne montée à +900 € puis redescendue à +120 €, et une ligne montée tout droit à
+120 €, s'y affichent à l'identique. C'est la première qui pose problème. Ces tests
vérifient que le module les distingue, et qu'il ne fabrique pas de chiffre quand il n'a
rien à mesurer.
"""

from __future__ import annotations

from packages.portfolio.pv_latente import agreger, pv_rendue


def _barres(prix: list[float], depart: int = 1) -> list[tuple[str, float]]:
    return [(f"2026-01-{depart + i:02d}", p) for i, p in enumerate(prix)]


def test_une_ligne_montee_puis_redescendue_est_distinguee_d_une_ligne_plate() -> None:
    """LE test. Même PV du jour, histoire opposée : c'est exactement ce que le tableau
    de bord ne pouvait pas montrer."""
    yoyo = pv_rendue(_barres([100.0, 190.0, 112.0]), "2026-01-01", 100.0, 10.0)
    droite = pv_rendue(_barres([100.0, 105.0, 112.0]), "2026-01-01", 100.0, 10.0)

    assert yoyo["pv_courante"] == droite["pv_courante"] == 120.0
    assert yoyo["rendu"] == 780.0 and droite["rendu"] == 0.0
    assert yoyo["part_rendue"] > 0.86 and droite["part_rendue"] == 0.0


def test_une_position_jamais_en_gain_ne_rend_rien() -> None:
    """Diviser par une PV maximale négative produirait une « part rendue » de signe
    arbitraire — un chiffre qui a l'air d'en être un."""
    perdante = pv_rendue(_barres([100.0, 90.0, 80.0]), "2026-01-01", 100.0, 10.0)
    assert perdante["jamais_en_gain"]
    assert perdante["part_rendue"] == 0.0
    assert perdante["pv_courante"] == -200.0


def test_les_barres_anterieures_a_l_entree_sont_ignorees() -> None:
    """Un pic atteint AVANT d'être en position n'a jamais été à personne."""
    avec_passe = pv_rendue(
        _barres([500.0, 100.0, 130.0]), entree="2026-01-02", prix_entree=100.0,
        quantite=10.0)
    assert avec_passe["pv_max"] == 300.0, avec_passe


def test_sans_barre_posterieure_a_l_entree_on_ne_conclut_pas() -> None:
    """On ne devine pas un prix courant à partir d'un prix d'entrée."""
    assert not pv_rendue(_barres([100.0]), "2026-06-01", 100.0, 10.0)["available"]
    assert not pv_rendue([], "2026-01-01", 100.0, 10.0)["available"]


def test_une_vente_a_decouvert_gagne_quand_le_cours_baisse() -> None:
    court = pv_rendue(_barres([100.0, 70.0, 90.0]), "2026-01-01", 100.0, 10.0,
                      sens="short")
    assert court["pv_max"] == 300.0
    assert court["pv_courante"] == 100.0
    assert court["rendu"] == 200.0


def test_le_total_ne_pretend_pas_que_les_pics_sont_simultanes() -> None:
    """Deux pics à deux dates différentes ne font pas un pic de portefeuille : la somme
    est un maximum théorique que le compte n'a jamais affiché. Le nom doit le dire."""
    a = pv_rendue(_barres([100.0, 200.0, 150.0]), "2026-01-01", 100.0, 1.0)
    b = pv_rendue(_barres([100.0, 80.0, 130.0]), "2026-01-01", 100.0, 1.0)

    total = agreger([a, b])
    assert total["n_positions"] == 2
    assert "somme_des_pics" in total and "pic_du_portefeuille" not in total
    assert total["somme_des_pics"] == 130.0     # +100 (a) et +30 (b), jamais ensemble
    assert total["pv_courante"] == 80.0            # +50 (a) et +30 (b), aujourd'hui


def test_un_total_sans_position_exploitable_ne_divise_pas_par_zero() -> None:
    assert agreger([{"available": False}])["part_rendue"] == 0.0
