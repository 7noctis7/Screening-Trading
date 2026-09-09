"""Un écart de moyennes ne dit pas s'il est réel — et un test qui ne peut pas conclure
doit le dire AVANT, pas laisser croire à une absence d'effet.

Ces tests portent sur les trois façons dont ce module pourrait tromper : conclure d'un
protocole sans puissance, comparer des fenêtres différentes des deux côtés, ou taire le
recouvrement qui rend sa p-valeur optimiste.
"""

from __future__ import annotations

import numpy as np

from packages.portfolio.duel_hors_echantillon import (
    decoupes,
    duel,
    p_minimale,
    performance_par_fenetre,
    recouvrement_ajustement,
)


def _perf(valeurs: list[float], debuts: list[int] | None = None) -> list[dict]:
    debuts = debuts or list(range(len(valeurs)))
    return [{"debut": d, "cvar": v, "rendement": 0.0, "pire": 0.0}
            for d, v in zip(debuts, valeurs, strict=True)]


def test_cinq_fenetres_ne_peuvent_pas_conclure_a_cinq_pour_cent() -> None:
    """LE chiffre qui manquait au run du 09/09.

    Le protocole 252/63 sur l'historique disponible ne donne que cinq fenêtres. Même en
    gagnant les cinq, la p-valeur vaut 0,0625 : le protocole ne PEUT PAS descendre sous
    5 %. Lire ce plancher comme une absence d'effet serait confondre « pas de preuve »
    et « preuve du contraire ».
    """
    assert p_minimale(5) == 0.0625
    parfait = duel(_perf([1.0] * 5), _perf([2.0] * 5))
    assert parfait["gagnees"] == 5
    assert parfait["p"] == 0.0625
    assert not parfait["concluant"], "conclut sur un protocole sans puissance"


def test_avec_assez_de_fenetres_un_avantage_net_conclut() -> None:
    """Contrôle positif : sans lui, un test qui ne conclut JAMAIS passerait aussi."""
    d = duel(_perf([1.0] * 16), _perf([2.0] * 16))
    assert d["gagnees"] == 16
    assert d["p"] < 0.001 and d["concluant"]


def test_un_avantage_moyen_porte_par_une_seule_fenetre_ne_conclut_pas() -> None:
    """LE piège que ce module existe pour attraper.

    Le candidat a une bien meilleure MOYENNE — une fenêtre catastrophique de la
    référence suffit — mais il perd cinq fenêtres sur six. Un agrégat mis bout à bout
    aurait dit « nettement meilleur » ; l'appariement dit « perdant ».
    """
    candidat = _perf([2.0, 2.0, 2.0, 2.0, 2.0, 2.0])
    reference = _perf([1.0, 1.0, 1.0, 1.0, 1.0, 30.0])
    moyenne = lambda lot: np.mean([x["cvar"] for x in lot])  # noqa: E731
    assert moyenne(candidat) < moyenne(reference), "contrôle inopérant : moyennes"

    d = duel(candidat, reference)
    assert d["gagnees"] == 1, d
    assert not d["concluant"]


def test_les_fenetres_non_partagees_sont_ecartees_des_deux_cotes() -> None:
    """Comparer un allocateur sur SES bonnes fenêtres à un autre sur toutes les siennes
    donnerait un avantage qui ne vient que du tri."""
    candidat = _perf([1.0, 1.0], debuts=[0, 2])       # la fenêtre 1 lui a échoué
    reference = _perf([2.0, 9.0, 2.0], debuts=[0, 1, 2])

    d = duel(candidat, reference)
    assert d["fenetres"] == 2, "une fenêtre non appariée a été comptée"
    assert d["gagnees"] == 2


def test_les_egalites_sortent_du_decompte() -> None:
    """Une égalité n'est ni une victoire ni une défaite : la compter fausse le test."""
    d = duel(_perf([1.0, 1.0, 5.0]), _perf([2.0, 2.0, 5.0]))
    assert d["fenetres"] == 3 and d["comparables"] == 2 and d["gagnees"] == 2


def test_le_recouvrement_des_ajustements_est_chiffre() -> None:
    """Il rend la p-valeur optimiste ; le taire serait publier une précision fausse."""
    assert recouvrement_ajustement(252, 63) == 0.75
    assert recouvrement_ajustement(252, 252) == 0.0


def test_les_segments_mesures_ne_se_recouvrent_jamais() -> None:
    """Les périodes d'AJUSTEMENT se recouvrent, les périodes MESURÉES non — sinon la
    même journée compterait plusieurs fois dans le décompte des victoires."""
    d = decoupes(1000, 252, 63)
    assert d == list(range(252, 938, 63))
    assert all(b - a >= 63 for a, b in zip(d, d[1:], strict=False))


def test_une_fenetre_ou_l_allocateur_echoue_est_absente_pas_inventee() -> None:
    """Remplacer un échec par une valeur de convenance ferait entrer dans le duel une
    performance que personne n'a mesurée."""
    g = np.random.default_rng(0)
    r = g.normal(0, 0.01, (400, 4))
    appels = {"n": 0}

    def capricieux(h):
        appels["n"] += 1
        if appels["n"] == 2:
            raise RuntimeError("solveur en échec")
        return [0.25] * h.shape[1]

    perf = performance_par_fenetre(r, capricieux, fenetre=252, pas=63)
    assert len(perf) == len(decoupes(400, 252, 63)) - 1
    assert all(np.isfinite(p["cvar"]) for p in perf)
