import numpy as np
import pytest

from packages.mandate import Mandat
from packages.portfolio.mandate_constraints import mandated_allocation


@pytest.mark.parametrize("method", ["erc", "min_var", "hrp"])
def test_trois_optimiseurs_respectent_les_bornes_du_mandat(method):
    cov = np.diag([0.01, 0.04, 0.09, 0.16])
    mandat = Mandat(
        moteur="preset",
        contraintes={
            "poids_min_ligne": 0.15,
            "poids_max_ligne": 0.35,
            "nb_lignes_min": 4,
        },
    )
    result = mandated_allocation(cov, ["A", "B", "C", "D"], mandat, method)
    assert sum(result.values()) == pytest.approx(1.0)
    assert all(0.15 <= weight <= 0.35 for weight in result.values())


def test_mandat_infaisable_est_un_veto_visible():
    mandat = Mandat(moteur="preset", contraintes={"poids_max_ligne": 0.2})
    with pytest.raises(ValueError, match="infaisables"):
        mandated_allocation(np.eye(3), ["A", "B", "C"], mandat)


def test_univers_interdit_est_refuse():
    mandat = Mandat(moteur="preset", contraintes={"univers_interdit": ["B"]})
    with pytest.raises(ValueError, match="interdit"):
        mandated_allocation(np.eye(2), ["A", "B"], mandat)
