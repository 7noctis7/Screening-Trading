"""Harnais « signal -> flux de rendements » : le protocole unique des candidats.

Deux risques, tous deux déjà survenus dans ce dépôt :

1. CAPTER LE RENDEMENT DE LA BARRE DÉCLENCHEUSE. Ça produit des courbes magnifiques et
   fausses (`channel_break`, corrigé en 3c1c771).
2. TRONQUER L'AXE À LA SÉRIE LA PLUS COURTE. Première version de ce harnais : l'axe
   valait `min(len(série))`, donc un titre de 265 barres réduisait la mesure à 14 jours
   pour les 785 autres. Les quatre candidats sont sortis « trop peu de jours » et le
   banc ne mesurait rien. Troisième occurrence de l'empilement positionnel, après
   `sector_momentum` et le preset.
"""

from datetime import UTC, datetime, timedelta

import pytest

from packages.research.flux_candidat import flux_quotidien

T0 = datetime(2015, 1, 1, tzinfo=UTC)


class _B:
    def __init__(self, ts, close):
        self.ts, self.close = ts, close


def _serie(closes, depart: int = 0):
    """Série datée. `depart` décale le PREMIER jour coté (titre plus jeune)."""
    return [_B(T0 + timedelta(days=depart + k), c) for k, c in enumerate(closes)]


def _data(n=400, sauts=()):
    px = [100.0] * n
    for i, amp in sauts:
        for k in range(i, n):
            px[k] *= 1 + amp
    return {"A": _serie(px), "B": _serie(px)}


# ------------------------------------------------------ l'axe est un CALENDRIER
def test_un_titre_JEUNE_ne_tronque_pas_la_mesure_des_autres():
    """LE test de non-régression. Un titre de 265 barres au milieu de titres de 400 ne
    doit RIEN retirer à la mesure : chacun est lu à sa propre position, à la date du
    jour. L'ancien axe `min(len)` ramenait tout le monde à 14 jours."""
    long_ = _serie([100.0 + k for k in range(400)])
    jeune = _serie([100.0 + k for k in range(265)], depart=135)   # cote tard
    r = flux_quotidien({"A": long_, "B": jeune}, lambda b: True, fenetre=250, pas=5)
    assert r["available"], r.get("motif")
    assert r["n_jours"] > 140                    # et non 14


def test_un_titre_ABSENT_un_jour_est_ecarte_et_non_compte_zero():
    """Compter zéro fabriquerait un rendement qui n'a pas eu lieu (règle du 01/09)."""
    montante = _serie([100 * (1.01 ** k) for k in range(400)])
    troue = [b for i, b in enumerate(montante) if i % 7]          # jours manquants
    r = flux_quotidien({"A": montante, "B": troue}, lambda b: True,
                       fenetre=250, pas=5, cout_bps=0.0)
    assert r["available"]
    assert r["rendements"][-1] == pytest.approx(0.01, abs=1e-9)


# ------------------------------------------------------------------ anti-fuite
def test_le_signal_ne_voit_QUE_le_passe():
    """Structurel : la fonction reçoit une fenêtre finissant à la date de décision."""
    vues = []

    def signal(barres):
        vues.append(len(barres))
        return True

    flux_quotidien(_data(), signal, fenetre=50, pas=5)
    assert vues and set(vues) == {50}


def test_le_rendement_de_la_barre_DECLENCHEUSE_n_est_PAS_capte():
    """Un signal qui s'allume exactement le jour d'un saut ne doit PAS l'encaisser :
    la décision est prise à la clôture de d, le rendement court de d à d+1."""
    data = _data(300, sauts=[(200, 0.50)])

    def signal_devin(barres):
        """S'allume UNIQUEMENT le jour du saut — le cas le plus favorable possible."""
        return len(barres) >= 2 and barres[-1].close / barres[-2].close - 1 > 0.4

    r = flux_quotidien(data, signal_devin, fenetre=50, pas=1, cout_bps=0.0)
    assert r["available"]
    assert max(r["rendements"]) < 0.01           # le +50 % n'est jamais encaissé


# ------------------------------------------------------------------- justesse
def test_un_signal_TOUJOURS_VRAI_reproduit_le_marche_equipondere():
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
    """Deux titres aux prix IDENTIQUES : l'écart ne peut venir que des frais."""
    data = _data(400)
    stable = flux_quotidien(data, lambda b: True, fenetre=50, pas=5, cout_bps=50.0)
    etat = {"appel": 0}

    def nerveux(barres):
        i = etat["appel"]
        etat["appel"] += 1
        decision, symbole = divmod(i, 2)
        return symbole == decision % 2           # on change de titre à chaque décision

    agite = flux_quotidien(data, nerveux, fenetre=50, pas=5, cout_bps=50.0)
    assert sum(stable["rendements"]) > sum(agite["rendements"])
    assert sum(stable["rendements"]) == pytest.approx(-0.005, abs=1e-9)   # une entrée


def test_un_calendrier_trop_court_est_REFUSE_et_non_bricole():
    r = flux_quotidien({"A": _serie([100.0] * 40)}, lambda b: True, fenetre=250)
    assert r["available"] is False


def test_un_univers_vide_ne_leve_pas():
    assert flux_quotidien({}, lambda b: True)["available"] is False
