"""Le gel d'IC : pas de features tant qu'aucun horizon ne bat la nulle."""

from packages.research.gel_ic import autoriser_features, juger, seuil_sidak


def _ligne(h, p, ic=0.02, p95=0.01):
    return {"horizon": h, "available": True, "p_signes": p, "ic_moyen": ic,
            "ic_premiere_moitie": ic, "ic_seconde_moitie": ic, "nulle_p95": p95}


def test_rien_de_mesure_gele_sans_ouvrir_un_essai():
    v = juger([{"horizon": 1, "available": False, "n_dates": 3}])
    assert v["statut"] == "UNCALIBRATED" and v["gele"] is True


def test_cinq_horizons_exigent_sidak_pas_cinq_pour_cent():
    """p = 0,04 ne suffit pas : les cinq horizons se lisent ensemble."""
    seuil = seuil_sidak(5)
    assert seuil < 0.05
    v = juger([_ligne(h, 0.04) for h in (1, 5, 10, 20, 60)])
    assert v["statut"] == "GELE" and v["n_qui_battent"] == 0


def test_un_horizon_qui_bat_vraiment_ouvre_sans_adopter():
    v = juger([_ligne(20, 0.001), _ligne(1, 0.9, ic=0.0) | {"available": False}])
    assert v["statut"] == "OUVERT" and v["horizons"] == [20] and v["gele"] is False


def test_les_deux_moities_doivent_avoir_le_meme_signe():
    r = _ligne(20, 0.001)
    r["ic_seconde_moitie"] = -0.02
    assert juger([r])["statut"] == "GELE"


def test_fichier_absent_interdit_le_labo(tmp_path):
    ok, msg = autoriser_features(tmp_path / "absent.json")
    assert ok is False and "UNCALIBRATED" in msg
