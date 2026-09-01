"""DDM : machine à états du dimensionnement en unités R (spec utilisateur, 01/09).

Ce que ces tests verrouillent en priorité, ce sont les cas où une lecture naïve de la
spec produirait un système DANGEREUX : compteurs non remis à zéro, série cassée par un
trade nul, stop collé à l'entrée, remontée symétrique.
"""

import pytest

from packages.risk.ddm import STATUT, MachineDDM, ReglesDDM, taille_position


def test_le_module_demarre_en_SHADOW():
    """Règle d'architecture : tout producteur non calibré a un poids capital NUL."""
    assert STATUT == "SHADOW_UNCALIBRATED"
    assert MachineDDM().etat()["statut"] == "SHADOW_UNCALIBRATED"


def test_descente_sur_4_pertes_consecutives():
    m = MachineDDM()
    assert m.risque_fractionnaire() == 0.01
    for _ in range(3):
        m.enregistrer(-1.0)
    assert m.niveau == 0, "3 pertes ne doivent PAS déclencher"
    m.enregistrer(-1.0)
    assert m.niveau == 1 and m.risque_fractionnaire() == 0.005


def test_descente_sur_moins_4R_meme_sans_serie():
    """L'autre branche du OU : des pertes entrecoupées de gains y mènent aussi."""
    m = MachineDDM()
    for p in (-2.0, +0.5, -2.0, -0.6):
        m.enregistrer(p)
    assert m.niveau == 1, m.etat()


def test_un_gain_casse_la_serie_de_pertes():
    m = MachineDDM()
    for _ in range(3):
        m.enregistrer(-0.2)
    m.enregistrer(+0.1)
    m.enregistrer(-0.2)
    assert m.niveau == 0 and m.pertes_consecutives == 1


def test_un_trade_NUL_ne_casse_aucune_serie():
    """Un P&L nul n'est ni un gain ni une perte. Le compter d'un côté fausserait les
    deux compteurs — et un breakeven est fréquent (sortie au seuil de rentabilité)."""
    m = MachineDDM()
    for _ in range(3):
        m.enregistrer(-1.0)
    m.enregistrer(0.0)
    assert m.pertes_consecutives == 3
    m.enregistrer(-1.0)
    assert m.niveau == 1


def test_les_compteurs_sont_REMIS_A_ZERO_au_changement_de_niveau():
    """LE piège. Sans remise à zéro, les −4R accumulés à DD0 compteraient encore à DD1
    et provoqueraient une seconde descente immédiate : le système tomberait à DD2 sur un
    seul épisode de pertes."""
    m = MachineDDM()
    for _ in range(4):
        m.enregistrer(-1.0)
    assert m.niveau == 1
    assert m.r_net_au_niveau == 0.0 and m.pertes_consecutives == 0


def test_descente_jusqu_a_DD2_puis_PLANCHER():
    """Le risque ne descend pas indéfiniment : DD2 est le dernier niveau."""
    m = MachineDDM()
    for _ in range(20):
        m.enregistrer(-1.0)
    assert m.niveau == 2 and m.risque_fractionnaire() == 0.0025


def test_remontee_par_4_gains():
    m = MachineDDM()
    for _ in range(4):
        m.enregistrer(-1.0)
    for _ in range(4):
        m.enregistrer(+1.0)
    assert m.niveau == 0


def test_la_remontee_est_ASYMETRIQUE():
    """Depuis DD2, il faut DEUX séries de 4 gains pour revenir à DD0 — une seule série
    ne saute pas deux niveaux. C'est ce qui empêche de re-risquer trop vite."""
    m = MachineDDM()
    for _ in range(8):
        m.enregistrer(-1.0)
    assert m.niveau == 2
    for _ in range(4):
        m.enregistrer(+1.0)
    assert m.niveau == 1, "une série de gains ne doit pas sauter deux niveaux"


def test_pas_de_remontee_au_dessus_de_DD0():
    m = MachineDDM()
    for _ in range(12):
        m.enregistrer(+1.0)
    assert m.niveau == 0 and m.risque_fractionnaire() == 0.01


# ------------------------------------------------------------------ sizing
def test_taille_position_formule():
    m = MachineDDM()
    assert taille_position(100_000, 50.0, 47.0, m) == pytest.approx(1000 / 3)


def test_taille_position_suit_le_niveau():
    m = MachineDDM()
    grand = taille_position(100_000, 50.0, 47.0, m)
    for _ in range(4):
        m.enregistrer(-1.0)
    assert taille_position(100_000, 50.0, 47.0, m) == pytest.approx(grand / 2)


def test_stop_colle_a_l_entree_rend_ZERO():
    """Une distance nulle donnerait une taille INFINIE. Renvoyer 0 est la seule réponse
    sûre — lever ferait tomber tout le run sur un cas de données."""
    m = MachineDDM()
    assert taille_position(100_000, 50.0, 50.0, m) == 0.0


def test_equity_negative_rend_ZERO():
    assert taille_position(-5.0, 50.0, 47.0, MachineDDM()) == 0.0


# ------------------------------------------------------------------ règles
def test_regles_invalides_refusees():
    with pytest.raises(ValueError):
        ReglesDDM(r_base=0.0)
    with pytest.raises(ValueError, match="décroître"):
        ReglesDDM(facteurs=(0.5, 1.0))
    with pytest.raises(ValueError):
        ReglesDDM(perte_jour_max=1.5)


def test_etat_est_lisible():
    m = MachineDDM()
    for _ in range(4):
        m.enregistrer(-1.0)
    e = m.etat()
    assert e["libelle"] == "DD1" and e["risque_pct"] == 0.5
    assert e["transitions"] == 1
