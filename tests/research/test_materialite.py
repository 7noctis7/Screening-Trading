"""Le poids des tranches négligeables — mesuré, jamais filtré en silence.

CE QUI A ÉTÉ VU À L'ÉCRAN (19/09). Des lignes à 0,00 $ de P&L avec un pourcentage non
nul. Rien n'est faux : ce sont de vraies tranches FIFO, de quantité si petite que leur
gain s'arrondit à zéro. Mais elles pèsent autant qu'un aller-retour de 5 000 $ dans le
taux de réussite et l'espérance par trade.
"""

from __future__ import annotations

from packages.research.materialite import poussieres


def _t(qty, prix, pnl):
    return {"qty": qty, "entry_price": prix, "pnl_net": pnl}


def test_la_mesure_porte_sur_le_NOTIONNEL_pas_sur_le_P_ET_L():
    """Un trade de 5 000 $ qui finit à 0,00 $ est un VRAI trade qui n'a rien rapporté.
    Le confondre avec une poussière effacerait le seul cas intéressant des deux."""
    r = poussieres([_t(20, 250.0, 0.0),            # 5 000 $ engagés, gain nul
                    _t(0.000001, 26.0, 0.0)])      # une poussière
    assert r["n"] == 1 and r["n_total"] == 2
    assert r["n_significatifs"] == 1


def test_les_deux_lectures_sont_PUBLIEES_cote_a_cote():
    """C'est une lecture, pas une correction : le lecteur doit pouvoir comparer les
    statistiques officielles à celles qui excluent les poussières."""
    fermes = [_t(10, 100.0, 50.0), _t(10, 100.0, -30.0),
              _t(1e-6, 26.0, 0.0), _t(1e-6, 26.0, 0.0), _t(1e-6, 26.0, 0.0)]
    r = poussieres(fermes)
    assert r["n"] == 3 and r["part_des_lignes"] == 0.6
    assert r["n_significatifs"] == 2
    assert r["win_rate_hors"] == 0.5, "1 gagnant sur 2 trades réels"
    assert r["esperance_hors"] == 10.0, "(50 − 30) / 2, et non / 5"


def test_un_realise_NUL_ne_produit_pas_de_part_inventee():
    """Rapporter à zéro donnerait l'infini ; publier 0 % ferait croire à une mesure."""
    r = poussieres([_t(1e-6, 26.0, 0.0), _t(1e-6, 26.0, 0.0)])
    assert r["part_du_realise"] is None
    assert r["win_rate_hors"] is None and r["n_significatifs"] == 0


def test_une_liste_VIDE_ne_casse_rien():
    r = poussieres([])
    assert r["n"] == 0 and r["n_total"] == 0 and r["part_des_lignes"] == 0.0
