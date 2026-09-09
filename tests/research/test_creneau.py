"""La décomposition nuit / journée doit être vérifiable, sinon elle n'apprend rien.

Le piège n'est pas dans la formule, il est dans les DONNÉES : si la clôture est corrigée
des splits et des dividendes et que l'ouverture ne l'est pas, chaque ajustement se loge
entièrement dans le rendement de nuit. On lit alors « la nuit fait tout le rendement »,
ce qui est exactement la conclusion attendue — et complètement fausse. D'où le contrôle
d'identité, qui est le vrai sujet de ces tests.
"""

from __future__ import annotations

import numpy as np
import pytest

from packages.research.creneau import coherence, decomposer


def _serie(nuits: list[float], journees: list[float]) -> tuple[np.ndarray, np.ndarray]:
    """Construit ouverture/clôture À PARTIR des rendements voulus : le test contrôle
    exactement ce qui s'est passé la nuit et ce qui s'est passé pendant la séance."""
    cloture, ouverture = [100.0], [100.0]
    for n, j in zip(nuits, journees, strict=True):
        o = cloture[-1] * (1.0 + n)
        ouverture.append(o)
        cloture.append(o * (1.0 + j))
    return np.array(ouverture)[:, None], np.array(cloture)[:, None]


def _fourchette(o: np.ndarray, c: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Haut et bas cohérents avec l'ouverture et la clôture fournies."""
    return np.maximum(o, c) * 1.001, np.minimum(o, c) * 0.999


def test_des_prix_coherents_ne_declenchent_rien() -> None:
    o, c = _serie([0.01, -0.02, 0.03], [0.005, 0.01, -0.015])
    h, b = _fourchette(o, c)
    assert coherence(o, h, b, c) == 0.0


def test_une_cloture_ajustee_et_une_ouverture_brute_sont_detectees() -> None:
    """LE test, et il a déjà servi une fois.

    Le premier garde-fou de ce module vérifiait l'identité
    `(1+nuit)(1+journée) = 1+total`. Ce test l'a démasquée : l'ouverture s'y simplifie,
    l'égalité tient pour n'importe quels nombres, et le désalignement passait à 0,0
    d'écart. Le contrôle qui mord regarde si l'ouverture et la clôture tombent dans la
    fourchette [bas, haut] de la séance — ce qu'aucune algèbre ne peut masquer.
    """
    o, c = _serie([0.01] * 5, [0.005] * 5)
    h, b = _fourchette(o, c)
    c_desaligne = c.copy()
    c_desaligne[3:] /= 2.0                       # clôture ajustée, ouverture non

    assert coherence(o, h, b, c) == 0.0, "contrôle inopérant : la base saine échoue"
    assert coherence(o, h, b, c_desaligne) > 0.3, "le désalignement passe inaperçu"


def test_la_nuit_et_la_journee_se_separent_bien() -> None:
    """Toute la performance la nuit, rien pendant la séance : la décomposition doit le
    dire, sinon elle ne sert à rien."""
    o, c = _serie([0.01] * 10, [0.0] * 10)
    d = decomposer(o, c)

    assert d["nuit"] == pytest.approx(1.01**10 - 1, rel=1e-9)
    assert d["journee"] == pytest.approx(0.0, abs=1e-12)
    assert d["part_nuit"] == pytest.approx(1.0, rel=1e-9)


def test_une_seance_qui_detruit_le_gain_de_la_nuit_depasse_cent_pour_cent() -> None:
    """Ce n'est pas une aberration : c'est le cas le plus souvent rapporté sur les
    actions américaines. La part de la nuit dépasse 100 % quand la séance perd."""
    o, c = _serie([0.02] * 10, [-0.01] * 10)
    d = decomposer(o, c)

    assert d["nuit"] > 0 and d["journee"] < 0
    assert d["part_nuit"] > 1.0, d["part_nuit"]


def test_un_actif_absent_ce_jour_la_ne_tire_pas_la_moyenne_vers_zero() -> None:
    """Un jour non coté n'est pas un jour à rendement nul : le compter ainsi diluerait
    mécaniquement toute performance vers zéro."""
    o, c = _serie([0.01] * 6, [0.0] * 6)
    o2, c2 = np.repeat(o, 2, axis=1), np.repeat(c, 2, axis=1)
    o2[3, 1], c2[3, 1] = np.nan, np.nan      # le second actif ne cote pas ce jour-là

    d = decomposer(o2, c2)
    assert d["nuit"] == pytest.approx(decomposer(o, c)["nuit"], rel=1e-9)


def test_le_masque_restreint_bien_le_perimetre() -> None:
    o_a, c_a = _serie([0.01] * 8, [0.0] * 8)
    o_b, c_b = _serie([-0.01] * 8, [0.0] * 8)
    o = np.column_stack([o_a[:, 0], o_b[:, 0]])
    c = np.column_stack([c_a[:, 0], c_b[:, 0]])

    assert decomposer(o, c, np.array([True, False]))["nuit"] > 0
    assert decomposer(o, c, np.array([False, True]))["nuit"] < 0
    assert not decomposer(o, c, np.array([False, False]))["available"]


def test_une_matrice_mal_formee_leve() -> None:
    z = np.zeros((4, 3))
    with pytest.raises(ValueError):
        coherence(z, z, z, np.zeros((4, 2)))
    with pytest.raises(ValueError):
        coherence(np.zeros(5), np.zeros(5), np.zeros(5), np.zeros(5))
    with pytest.raises(ValueError):
        decomposer(np.zeros((1, 3)), np.zeros((1, 3)))
