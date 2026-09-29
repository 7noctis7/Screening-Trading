"""QML-015 — un gap sous le stop s'exécute à l'OUVERTURE, pas au prix du stop.

`_sortie` rendait `stop_dur` dès que `low <= stop`. Si la barre ouvre déjà sous le stop (gap
baissier), aucun ordre n'a pu passer au prix du stop : la sortie réelle se fait à
l'ouverture, plus bas. Supposer le stop exécuté embellissait chaque gap défavorable.
"""

from datetime import UTC, datetime

from packages.core.models import Bar


def _barre(o, h, lo, c):
    return Bar("X", "1d", datetime(2020, 1, 2, tzinfo=UTC), o, h, lo, c, 1e6)


def _position():
    return {"stop": 95.0, "target": 130.0, "hh": 100.0, "entry_price": 100.0}


def test_gap_sous_le_stop_sort_a_l_ouverture():
    from packages.backtest.fast_swing import _sortie
    px, motif = _sortie(_barre(90.0, 92.0, 88.0, 91.0), _position(), 2.0, float("nan"), 0.0)
    assert motif == "stop_hit" and px == 90.0


def test_stop_touche_en_seance_sort_au_stop():
    from packages.backtest.fast_swing import _sortie
    px, _ = _sortie(_barre(98.0, 99.0, 94.0, 96.0), _position(), 2.0, float("nan"), 0.0)
    assert px == 95.0


def test_gap_au_dessus_de_la_cible_ne_rend_que_la_cible():
    """Symétrie PRUDENTE : un gap haussier au-delà de la cible n'est pas crédité au-delà
    de la cible (ordre limite) — comportement historique, conservé."""
    from packages.backtest.fast_swing import _sortie
    px, motif = _sortie(_barre(140.0, 141.0, 139.0, 140.0), _position(), 2.0, float("nan"), 0.0)
    assert motif == "target_hit" and px == 130.0
