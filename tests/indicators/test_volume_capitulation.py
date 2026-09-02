"""Capitulation sur volume — le premier candidat OPPOSÉ au signal de production.

La production exige cours > MM50 croissante ; celui-ci exige cours < MM20 < MM50 <
MM100 < MM200. C'est la seule propriété qui fasse monter un Sharpe combiné, et c'est
pour ça que ce candidat mérite un test soigné plutôt qu'un câblage rapide.

Trois risques, tous déjà rencontrés dans ce dépôt :
  · utiliser la semaine EN COURS comme si elle était close (son volume cumulé est
    partiel — on raterait le pic, ou on en inventerait un) ;
  · chercher le pic APRÈS coup, ce qui regarde le futur ;
  · un test qui passe pour une mauvaise raison, parce que le générateur de données ne
    groupe pas les semaines comme le code (erreur commise en écrivant ces tests).
"""

from datetime import UTC, datetime, timedelta

import pytest

from packages.indicators.volume_capitulation import (
    empilement_baissier,
    hebdomadaire,
    pic_de_volume,
    proche_des_bas,
    signal,
    volume_croissant,
)

LUNDI = datetime(2018, 1, 1, tzinfo=UTC)


class _B:
    def __init__(self, ts, o, h, b, c, v):
        self.ts, self.open, self.high = ts, o, h
        self.low, self.close, self.volume = b, c, v


def _serie(n=1600, pic=None, croissant=True, pente=-0.09):
    """Série quotidienne. `pic` est un indice de SEMAINE (7 jours calendaires ici)."""
    out = []
    for k in range(n):
        px = 200.0 + k * pente
        v, sem = 1e6, k // 7
        if pic is not None:
            if sem == pic:
                v = 6e6
            elif croissant and pic < sem <= pic + 3:
                v = 6e6 + (sem - pic) * 1e6
        out.append(_B(LUNDI + timedelta(days=k), px, px * 1.01, px * 0.99, px, v))
    return out


def _pic_confirmable(n=1600):
    """Semaine telle que le pic tombe 3 semaines avant la dernière semaine close."""
    return len(hebdomadaire(_serie(n))) - 4


# --------------------------------------------------- la semaine EN COURS est partielle
def test_la_semaine_INCOMPLETE_est_ecartee():
    """Son volume cumulé n'est pas comparable à celui d'une semaine pleine. La traiter
    comme close sous-estimerait son volume — et ferait rater le pic.

    1601 jours depuis un lundi finissent un VENDREDI : la dernière semaine est donc
    close et conservée. En retirer deux jours la fait finir un mercredi, et elle doit
    alors disparaître. (Une série de 1600 jours finit un jeudi — sa dernière semaine
    était déjà écartée, si bien que le test n'aurait rien prouvé.)"""
    vendredi = _serie(1601)
    assert vendredi[-1].ts.weekday() == 4
    mercredi = vendredi[:-2]
    assert len(hebdomadaire(mercredi)) == len(hebdomadaire(vendredi)) - 1


def test_une_semaine_CLOSE_le_vendredi_est_conservee():
    """Contre-épreuve : sans elle, on jetterait une semaine valide sur deux."""
    complet = _serie(1600)
    jusqu_au_vendredi = [b for b in complet if b.ts.weekday() <= 4]
    assert len(hebdomadaire(jusqu_au_vendredi)) == len(hebdomadaire(complet))


def test_le_volume_hebdomadaire_est_la_SOMME_des_jours():
    sem = hebdomadaire(_serie(70))
    assert sem[0].volume == pytest.approx(7e6)   # 7 jours à 1e6


# ------------------------------------------------------------------- les conditions
def test_le_cas_COMPLET_declenche():
    assert signal(_serie(1600, pic=_pic_confirmable())) is True


@pytest.mark.parametrize("manquant", ["pic", "croissance", "tendance"])
def test_chaque_condition_est_NECESSAIRE(manquant):
    """Sans ces contre-épreuves, le test précédent ne prouverait rien."""
    pic = _pic_confirmable()
    if manquant == "pic":
        b = _serie(1600)                                   # aucun pic de volume
    elif manquant == "croissance":
        b = _serie(1600, pic=pic, croissant=False)         # pic isolé, sans suite
    else:
        b = _serie(1600, pic=pic, pente=+0.09)             # tendance HAUSSIÈRE
    assert signal(b) is False


def test_l_empilement_est_bien_l_INVERSE_du_filtre_de_production():
    """La production exige cours > MM50 croissante. Une série haussière doit donc être
    refusée ici — c'est la propriété qui rend ce candidat potentiellement orthogonal."""
    baissiere = [x.close for x in hebdomadaire(_serie(1600, pente=-0.09))]
    haussiere = [x.close for x in hebdomadaire(_serie(1600, pente=+0.09))]
    assert empilement_baissier(baissiere) is True
    assert empilement_baissier(haussiere) is False


# ------------------------------------------------------------------------ anti-fuite
def test_le_pic_ne_se_cherche_PAS_dans_le_futur():
    """Le pic est cherché exactement `confirmations` semaines avant la dernière
    semaine close. Un pic plus TARDIF, donc non encore confirmable, ne déclenche pas."""
    trop_recent = _pic_confirmable() + 2
    assert signal(_serie(1600, pic=trop_recent)) is False


def test_la_reference_du_pic_est_le_PASSE_et_rien_que_lui():
    """Deux démonstrations, parce qu'une seule se prête à l'illusion.

    D'abord la référence EST le passé : un passé plat rend tout excès détectable, un
    passé qui contient déjà un gros volume relève le seuil et absorbe le suivant."""
    assert pic_de_volume([1e6] * 20 + [1.1e6], 20) is True       # passé plat
    assert pic_de_volume([1e6] * 19 + [5e6] + [1.1e6], 20) is False   # absorbé


def test_le_verdict_du_pic_ne_depend_PAS_des_barres_FUTURES():
    """L'anti-fuite, et c'est la propriété qui compte vraiment. Ce qui vient APRÈS la
    semaine testée ne doit jamais entrer dans son verdict."""
    base = [1e6] * 20 + [3e6]
    assert pic_de_volume(base + [1e6], 20) == pic_de_volume(base + [1e9], 20)


# ------------------------------------------------------------- « zone de bon prix »
def test_la_zone_de_BON_PRIX_est_definie_et_bornee():
    """La spécification disait « proche des plus bas », ce qui ne s'exécute pas. Le
    seuil retenu est un paramètre, et il doit trancher dans les deux sens."""
    bas = [100.0] * 52
    assert proche_des_bas(bas, 110.0, part=0.15) is True
    assert proche_des_bas(bas, 130.0, part=0.15) is False


def test_un_historique_trop_court_ne_declenche_jamais():
    for n in (0, 50, 500):
        assert signal(_serie(n)) is False


def test_volume_croissant_refuse_une_seule_baisse():
    assert volume_croissant([1, 2, 3, 4, 5], 0, 3) is True
    assert volume_croissant([1, 2, 1, 4, 5], 0, 3) is False
