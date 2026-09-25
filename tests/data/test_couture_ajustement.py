"""QML-016 — la jonction « base longue → maj quotidienne » ne fabrique pas de rendement.

`YAHOO.db` est ajustée à la date de son export ; `market.db` est ré-ajustée à chaque
split/dividende (`ingest_prices._split_drift`). Après un split 10:1 postérieur à l'export,
la base longue reste à 1 000 $ et la maj repart à 100 $ : fusionnées telles quelles, elles
fabriquent un −90 % le jour de la jonction. Là où les deux bases se recouvrent, leur
rapport de cours révèle le facteur ; on remet l'historique long dans le référentiel de la
base à jour. Multiplier un segment par une constante ne change aucun rendement interne.
"""

from datetime import UTC, datetime, timedelta

import pytest

from packages.core.models import Bar

D0 = datetime(2024, 1, 1, tzinfo=UTC)


def _barres(prix, debut=0):
    return [Bar("X", "1d", D0 + timedelta(days=debut + i), p, p, p, p, 1e6)
            for i, p in enumerate(prix)]


def test_split_posterieur_a_l_export_rebase_la_base_longue():
    from packages.data.fusion_sources import rebaser_base_longue
    longue = _barres([1000.0, 1010.0, 1020.0, 1030.0, 1040.0])        # jours 0-4, non ajustée
    maj = _barres([102.0, 103.0, 104.0, 105.0], debut=2)               # jours 2-5, ajustée /10
    rebasee, facteur = rebaser_base_longue(longue, maj)
    assert facteur == pytest.approx(0.1)
    assert [b.close for b in rebasee] == pytest.approx([100.0, 101.0, 102.0, 103.0, 104.0])


def test_bases_d_accord_rien_ne_bouge():
    from packages.data.fusion_sources import rebaser_base_longue
    longue = _barres([100.0, 101.0, 102.0])
    maj = _barres([101.0, 102.0, 103.0], debut=1)
    rebasee, facteur = rebaser_base_longue(longue, maj)
    assert facteur is None and rebasee is longue


def test_desaccord_non_constant_n_est_pas_un_ajustement():
    """Un rapport qui varie d'un jour à l'autre n'est pas un facteur d'ajustement : on ne
    touche à rien (le diagnostic `make diag-fusion` reste l'outil pour enquêter)."""
    from packages.data.fusion_sources import rebaser_base_longue
    longue = _barres([100.0, 100.0, 100.0, 100.0])
    maj = _barres([90.0, 110.0, 95.0], debut=1)
    assert rebaser_base_longue(longue, maj)[1] is None


def test_sans_recouvrement_rien_ne_bouge():
    from packages.data.fusion_sources import rebaser_base_longue
    longue = _barres([100.0, 101.0])
    assert rebaser_base_longue(longue, _barres([50.0], debut=10))[1] is None
