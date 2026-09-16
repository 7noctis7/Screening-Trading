"""Le disjoncteur du fournisseur LLM — trois états, une horloge injectée.

Sans lui : fournisseur éteint = deux cents titres × douze secondes de délai, soit quarante
minutes à ne rien faire, pendant que le reste de l'analyse attend.
"""

from packages.nlp.disjoncteur import ENTROUVERT, FERME, OUVERT, Disjoncteur


def _horloge():
    t = [0.0]
    return t, (lambda: t[0])


def _dj(seuil=2, refroid=10.0):
    t, h = _horloge()
    return t, Disjoncteur(seuil=seuil, refroidissement_s=refroid, _horloge=h)


def test_ferme_au_depart():
    _, d = _dj()
    assert d.etat() == FERME and d.autorise()


def test_un_echec_isole_n_ouvre_pas():
    """Une erreur ponctuelle n'est pas une panne. Ouvrir dès le premier échec priverait
    de NLP pour une seconde de réseau."""
    _, d = _dj(seuil=2)
    d.echec()
    assert d.etat() == FERME and d.autorise()


def test_un_succes_remet_le_compteur_a_zero():
    """Ce sont les échecs CONSÉCUTIFS qui comptent : deux échecs séparés par un succès
    décrivent un service qui fonctionne, pas un service mort."""
    _, d = _dj(seuil=2)
    d.echec()
    d.succes()
    d.echec()
    assert d.etat() == FERME


def test_le_seuil_ouvre_le_circuit():
    _, d = _dj(seuil=2)
    d.echec()
    d.echec()
    assert d.etat() == OUVERT and not d.autorise()


def test_ouvert_rend_la_main_immediatement():
    """C'est toute la raison d'être : ne PAS attendre le délai quand on sait déjà."""
    _, d = _dj(seuil=1)
    d.echec()
    assert all(not d.autorise() for _ in range(50))


def test_le_refroidissement_fait_passer_en_entrouvert():
    t, d = _dj(seuil=1, refroid=10.0)
    d.echec()
    t[0] = 9.9
    assert d.etat() == OUVERT
    t[0] = 10.0
    assert d.etat() == ENTROUVERT


def test_entrouvert_ne_laisse_passer_qu_UN_essai():
    """Rouvrir en grand enverrait deux cents requêtes vers un service qui vient de
    redémarrer — on le referait tomber avec la charge envoyée pour le tester."""
    t, d = _dj(seuil=1, refroid=10.0)
    d.echec()
    t[0] = 11.0
    assert d.autorise() is True
    assert d.autorise() is False
    assert d.autorise() is False


def test_un_essai_reussi_referme_le_circuit():
    t, d = _dj(seuil=1, refroid=10.0)
    d.echec()
    t[0] = 11.0
    d.autorise()
    d.succes()
    assert d.etat() == FERME and d.autorise()


def test_un_essai_rate_rouvre_pour_un_cycle_COMPLET():
    """Sinon on repartirait en rafale de tentatives sur un service toujours mort."""
    t, d = _dj(seuil=3, refroid=10.0)
    for _ in range(3):
        d.echec()
    t[0] = 11.0
    d.autorise()
    d.echec()
    assert d.etat() == OUVERT
    t[0] = 15.0
    assert d.etat() == OUVERT          # le refroidissement a REDÉMARRÉ
    t[0] = 21.1
    assert d.etat() == ENTROUVERT


def test_l_etat_public_dit_le_temps_restant():
    t, d = _dj(seuil=1, refroid=60.0)
    d.echec()
    t[0] = 20.0
    p = d.etat_public()
    assert p["etat"] == OUVERT and 39.0 <= p["reouverture_dans_s"] <= 41.0


def test_reinitialiser_repart_de_zero():
    _, d = _dj(seuil=1)
    d.echec()
    d.reinitialiser()
    assert d.etat() == FERME and d.autorise()


def test_l_etat_n_est_pas_persiste():
    """Un disjoncteur qui survit au processus décrirait l'état d'un service tel qu'il
    était à l'arrêt précédent — ce qui n'apprend rien sur maintenant."""
    import pathlib
    src = (pathlib.Path(__file__).resolve().parents[2] / "packages" / "nlp"
           / "disjoncteur.py").read_text(encoding="utf-8")
    for interdit in ("open(", "Path(", "json.dump", "pickle"):
        assert interdit not in src
