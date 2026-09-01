"""Harnais « signal -> flux de rendements » : le protocole unique des candidats.

Le risque de cette classe de code est unique et grave : capter le rendement de la barre
qui a DÉCLENCHÉ le signal. Ça produit des courbes magnifiques et fausses, et ça s'est
déjà produit dans ce dépôt (`channel_break`, corrigé en 3c1c771). Les deux premiers
tests ne testent que cela.
"""

import pytest

from packages.research.flux_candidat import flux_quotidien


class _B:
    def __init__(self, close):
        self.close = close


def _serie(closes):
    return [_B(c) for c in closes]


def _data(n=400, sauts=()):
    """Marché plat à 100, avec des sauts ponctuels d'un jour à des indices donnés."""
    px = [100.0] * n
    for i, amp in sauts:
        for k in range(i, n):
            px[k] *= 1 + amp
    return {"A": _serie(px), "B": _serie(px)}


def test_le_signal_ne_voit_QUE_le_passe():
    """Structurel : la fonction reçoit une fenêtre finissant à t. Si elle voyait plus
    loin, ce test le dirait — on enregistre la longueur reçue à chaque appel."""
    vues = []

    def signal(barres):
        vues.append(len(barres))
        return True

    flux_quotidien(_data(), signal, fenetre=50, pas=5)
    assert vues and set(vues) == {50}


def test_le_rendement_de_la_barre_DECLENCHEUSE_n_est_PAS_capte():
    """Un signal qui s'allume exactement le jour d'un saut ne doit PAS encaisser ce
    saut : la décision est prise à la clôture de t, le rendement court de t à t+1."""
    n, i_saut = 300, 200
    data = _data(n, sauts=[(i_saut, 0.50)])       # +50 % à l'indice 200

    def signal_devin(barres):
        """S'allume UNIQUEMENT le jour du saut — le cas le plus favorable possible."""
        return len(barres) >= 2 and barres[-1].close / barres[-2].close - 1 > 0.4

    r = flux_quotidien(data, signal_devin, fenetre=50, pas=1, cout_bps=0.0)
    assert r["available"]
    assert max(r["rendements"]) < 0.01           # le +50 % n'est jamais encaissé


def test_un_signal_TOUJOURS_VRAI_reproduit_le_marche_equipondere():
    """Contrôle de justesse : sans sélection, le flux doit être celui du marché."""
    data = {"A": _serie([100 * (1.001 ** k) for k in range(400)])}
    r = flux_quotidien(data, lambda b: True, fenetre=50, pas=5, cout_bps=0.0)
    assert r["rendements"][10] == pytest.approx(0.001, abs=1e-9)
    assert r["part_investie"] == 1.0


def test_un_signal_TOUJOURS_FAUX_donne_un_flux_NUL_et_non_vide():
    """Zéro n'est pas « indisponible » : rester à l'écart est une décision, et son
    rendement est zéro. Renvoyer une série vide fausserait toute comparaison."""
    r = flux_quotidien(_data(), lambda b: False, fenetre=50, pas=5)
    assert r["available"] and set(r["rendements"]) == {0.0}
    assert r["part_investie"] == 0.0


def test_les_COUTS_ne_frappent_que_la_ROTATION():
    """Un signal stable ne paie qu'à l'entrée ; un signal qui change de titre à chaque
    décision paie à chaque fois. Sans cette distinction, un signal nerveux paraîtrait
    aussi bon qu'un signal stable — et il ne l'est jamais, une fois les frais comptés.

    Les deux titres ont ici des prix IDENTIQUES : l'écart mesuré ne peut donc venir que
    des frais de rotation, jamais d'une meilleure sélection."""
    data = _data(400)
    stable = flux_quotidien(data, lambda b: True, fenetre=50, pas=5, cout_bps=50.0)

    etat = {"appel": 0}

    def nerveux(barres):
        i = etat["appel"]
        etat["appel"] += 1
        decision, symbole = divmod(i, 2)         # 2 titres dans l'univers
        return symbole == decision % 2           # on change de titre à chaque décision

    agite = flux_quotidien(data, nerveux, fenetre=50, pas=5, cout_bps=50.0)
    assert sum(stable["rendements"]) > sum(agite["rendements"])
    assert sum(stable["rendements"]) == pytest.approx(-0.005, abs=1e-9)   # une entrée


def test_une_serie_trop_courte_est_REFUSEE_et_non_bricolee():
    r = flux_quotidien({"A": _serie([100.0] * 40)}, lambda b: True, fenetre=250)
    assert r["available"] is False


def test_une_barre_MANQUANTE_est_ecartee_et_non_comptee_zero():
    """Compter zéro fabriquerait un rendement qui n'a pas eu lieu (règle du 01/09)."""
    montante = _serie([100 * (1.01 ** k) for k in range(400)])
    data = {"A": montante, "B": montante[:300]}   # B s'arrête en cours de route
    r = flux_quotidien(data, lambda b: True, fenetre=50, pas=5, cout_bps=0.0)
    assert r["rendements"][-1] == pytest.approx(0.01, abs=1e-9)
