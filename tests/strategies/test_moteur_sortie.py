"""Moteur de sortie : l'invariant du stop, l'ordre pessimiste, la fenêtre de temps.

Le test central de ce fichier n'est pas une sortie mais une NON-action : le stop ne doit
jamais bouger sans invalidant structurel. C'est la règle qu'un moteur de sortie perd en
premier, et la seule dont la perte ne se voit pas dans les chiffres avant longtemps.
"""

from dataclasses import dataclass

import pytest

from packages.strategies.moteur_sortie import (
    ExitEngine,
    Position,
    cvd_proxy,
    delta_signe,
    divergence_baissiere,
)


@dataclass
class B:
    open: float
    high: float
    low: float
    close: float
    volume: float


def _zigzag(n: int, base: float = 100.0, pente: float = 0.0, amp: float = 3.0,
            vol: float = 1000.0):
    out = []
    for i in range(n):
        phase = i % 10
        p = base + pente * i + amp * (phase if phase <= 5 else 10 - phase)
        out.append(B(p, p + 1.0, p - 1.0, p, vol))
    return out


# Série CONSTRUITE pour produire une divergence : le prix fait un sommet plus haut
# (113 → 117) pendant que le CVD approché DÉCROÎT (6 300 → -2 100), parce que toutes
# les barres postérieures au premier sommet clôturent dans le bas de leur amplitude.
# Une divergence prise « au hasard » sur une série aléatoire ne testerait rien.
_NIVEAUX = [100, 102, 104, 106, 108, 110, 112, 110, 108, 106, 104, 102, 100, 102,
            104, 106, 108, 110, 112, 114, 116, 114, 112, 110, 108, 106]


def _divergente() -> list[B]:
    return [B(float(p), p + 1.0, p - 1.0, (p + 0.9 if k <= 6 else p - 0.6), 1000.0)
            for k, p in enumerate(_NIVEAUX)]


def _pos(**kw) -> Position:
    d = {"symbole": "X", "sens": "long", "entree": 100.0, "stop_initial": 96.0,
         "quantite": 100.0, "index_entree": 60}
    d.update(kw)
    return Position(**d)


def test_une_position_sans_distance_au_stop_est_refusee_a_la_construction():
    """Une distance nulle donnerait une taille infinie, pas une erreur visible."""
    with pytest.raises(ValueError):
        _pos(stop_initial=100.0)


def test_le_multiple_de_r_est_fige_a_l_entree_meme_apres_deplacement_du_stop():
    """1R est une unité de mesure, pas une distance courante : la déplacer réécrirait
    tous les R passés du journal."""
    p = _pos()
    assert p.multiple_r(108.0) == 2.0
    p.stop_courant = 99.0
    assert p.multiple_r(108.0) == 2.0


def test_le_stop_ne_bouge_que_sur_un_invalidant_structurel():
    """L'interdiction du breakeven de confort. Aucun gain, si grand soit-il, ne suffit.

    Sur la série divergente il existe un creux confirmé à 99, validé par un sommet
    POSTÉRIEUR : le stop passe donc de 96 à 99 — pour une raison de structure, jamais
    parce que la position est en gain de 2R au même moment.
    """
    bars = _divergente()
    m = ExitEngine()
    p = _pos(entree=99.0, stop_initial=96.0, index_entree=20)
    assert m.invalidant_structurel(p, bars, len(bars) - 1) == 99.0
    m.appliquer(p, m.evaluer(p, bars, len(bars) - 1))
    assert p.stop_courant == 99.0


def test_aucun_invalidant_sans_sommet_posterieur_au_creux():
    """Un creux plus haut sans nouveau sommet derrière est une pause, pas une structure."""
    bars = _divergente()[:14]                          # s'arrête avant le second sommet
    m = ExitEngine()
    p = _pos(entree=99.0, stop_initial=96.0, index_entree=5)
    assert m.invalidant_structurel(p, bars, len(bars) - 1) is None


def test_le_stop_ne_recule_jamais_meme_si_l_appelant_le_demande():
    """Le garde-fou vit dans `appliquer`, pas seulement dans la détection."""
    p = _pos()
    m = ExitEngine()
    m.appliquer(p, {"actions": [{"type": "stop_deplace", "de": 96.0, "vers": 98.0,
                                 "motif": "structure"}]})
    assert p.stop_courant == 98.0
    m.appliquer(p, {"actions": [{"type": "stop_deplace", "de": 98.0, "vers": 97.0,
                                 "motif": "structure"}]})
    assert p.stop_courant == 98.0                      # jamais en arrière


def test_le_stop_prime_sur_la_cible_quand_la_barre_touche_les_deux():
    """Des barres quotidiennes ne disent pas l'ordre intrabar. On retient le pire."""
    bars = _zigzag(80)
    bars.append(B(100.0, 500.0, 50.0, 200.0, 1000.0))  # touche tout
    p = _pos(index_entree=79)
    r = ExitEngine().evaluer(p, bars, 80)
    assert r["cloture"] and r["actions"][0]["type"] == "stop"


def test_sortie_de_temps_forcee_au_quinzieme_jour():
    bars = _zigzag(120)
    p = _pos(entree=float(bars[60].close), stop_initial=float(bars[60].close) - 50.0,
             index_entree=60)
    m = ExitEngine(duree_max=15)
    assert m.evaluer(p, bars, 74)["cloture"] is False       # 14 séances
    r = m.evaluer(p, bars, 75)                              # 15 séances
    assert r["cloture"] and r["actions"][-1]["type"] == "temps"
    assert r["actions"][-1]["prix"] == float(bars[75].close)


def test_la_borne_basse_de_la_fenetre_est_reportee_jamais_bloquante():
    """« 2 à 15 jours » décrit un horizon. En verrou, il coûterait un gain offert au J1."""
    bars = _zigzag(80)
    bars.append(B(100.0, 400.0, 99.0, 390.0, 1000.0))       # cible atteinte tout de suite
    p = _pos(index_entree=80)
    r = ExitEngine().evaluer(p, bars, 80)
    assert r["hors_fenetre_nominale"] is True               # signalé…
    assert r["cloture"] is True                             # …mais la sortie a lieu


def test_la_cible_retient_le_plus_exigeant_des_deux_criteres():
    """Sommet majeur ET plancher en R : le plus loin des deux, jamais le plus proche."""
    bars = _zigzag(80, base=100.0, amp=1.0)                 # sommets ~106 max
    p = _pos(entree=100.0, stop_initial=96.0, index_entree=79)
    cible = ExitEngine(r_cible_min=3.0).cible_liquidite(p, bars, 79)
    assert cible >= 112.0                                   # 100 + 3 × 4, le plancher gagne


def test_delta_signe_vaut_le_volume_sur_une_cloture_au_plus_haut():
    assert delta_signe(B(10, 12, 8, 12, 1000.0)) == 1000.0
    assert delta_signe(B(10, 12, 8, 8, 1000.0)) == -1000.0
    assert delta_signe(B(10, 12, 8, 10, 1000.0)) == 0.0


def test_cvd_ne_lit_aucune_barre_posterieure():
    bars = _zigzag(60)
    partiel = cvd_proxy(bars, 30)
    complet = cvd_proxy(bars)
    assert partiel == complet[:31]


def test_divergence_exige_deux_sommets_confirmes_et_un_nouveau_plus_haut():
    bars = _divergente()
    d = divergence_baissiere(bars, len(bars) - 1)
    assert d["divergence"] is True
    assert d["sommet_courant"] > d["sommet_precedent"]      # le prix, lui, progresse
    assert d["cvd_courant"] < d["cvd_precedent"]            # le flux ne suit pas
    petit = divergence_baissiere(_zigzag(12), 11)
    assert petit["divergence"] is False
    assert "deux sommets" in petit["motif"]


def test_pas_de_divergence_quand_le_flux_confirme_le_nouveau_sommet():
    """Le cas symétrique : mêmes prix, clôtures FORTES — la règle ne doit pas mordre."""
    bars = [B(float(p), p + 1.0, p - 1.0, p + 0.9, 1000.0) for p in _NIVEAUX]
    d = divergence_baissiere(bars, len(bars) - 1)
    assert d["divergence"] is False
    assert "confirme" in d["motif"]


def test_la_partielle_se_declenche_a_2r_sur_divergence_et_une_seule_fois():
    bars = _divergente()
    i = len(bars) - 1
    p = _pos(entree=99.0, stop_initial=96.0, index_entree=20)
    m = ExitEngine()
    r = m.evaluer(p, bars, i)
    assert r["r_courant"] >= 2.0 and r["cloture"] is False
    partielle = next(a for a in r["actions"] if a["type"] == "partielle")
    assert partielle["quantite"] == 50.0                   # 50 % de 100
    m.appliquer(p, r)
    assert p.partielle_prise is True and p.quantite_restante == 50.0
    assert m._partielle(p, bars, i) is None                # jamais deux fois


def test_atteindre_2r_sans_divergence_ne_declenche_aucune_partielle():
    """C'est tout l'objet de la règle : le gain seul n'autorise rien."""
    bars = [B(float(p), p + 1.0, p - 1.0, p + 0.9, 1000.0) for p in _NIVEAUX]
    i = len(bars) - 1
    p = _pos(entree=99.0, stop_initial=96.0, index_entree=20)
    r = ExitEngine().evaluer(p, bars, i)
    assert r["r_courant"] >= 2.0
    assert not [a for a in r["actions"] if a["type"] == "partielle"]
