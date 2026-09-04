"""Ciblage de volatilité (Moreira & Muir, JF 2017) — le seul levier de Sharpe qui ne
demande AUCUN signal directionnel nouveau.

La raison tient en une phrase : la volatilité est PRÉVISIBLE (elle s'agglutine), les
rendements ne le sont pas. Baisser la voile quand ça s'agite et la remonter quand ça se
calme réduit la variance plus que le rendement.

Le risque de cette classe de code est UNIQUE et il est grave : utiliser la volatilité du
jour même pour décider de l'exposition du jour même. C'est du look-ahead, et il produit
des courbes magnifiques et fausses. Le premier test ci-dessous ne teste que cela.
"""

import pytest

from packages.backtest.fast_swing import _expo_vol_cible


def _equity(rendements, depart=10_000.0):
    eq, v = [depart], depart
    for r in rendements:
        v *= 1 + r
        eq.append(v)
    return eq


def test_AUCUNE_FUITE_le_choc_du_jour_ne_change_pas_l_exposition_du_jour():
    """LE test. `equity` ne contient que les barres closes jusqu'à t−1 : ajouter un
    krach APRÈS coup ne doit rien changer à la décision déjà prise."""
    calme = [0.001] * 40
    avant = _expo_vol_cible(_equity(calme), 0.15, 20)
    apres = _expo_vol_cible(_equity(calme + [-0.20]), 0.15, 20)
    assert avant == pytest.approx(1.0)      # marché calme : pleine exposition
    assert apres < avant                    # le krach ne compte qu'au tour SUIVANT


def test_un_marche_AGITE_reduit_l_exposition():
    import numpy as np
    agite = list(np.random.default_rng(0).normal(0.0, 0.04, 60))    # ~63 % annualisés
    e = _expo_vol_cible(_equity(agite), 0.15, 20)
    assert 0.0 < e < 0.4


def test_un_marche_CALME_ne_depasse_jamais_100_pour_cent():
    """Règle du dépôt : sans levier. Une vol réalisée minuscule ne doit pas ouvrir
    l'exposition au-delà de 1,0, même si la formule le suggère."""
    import numpy as np
    calme = list(np.random.default_rng(0).normal(0.0, 0.001, 60))   # ~1,6 % annualisés
    assert _expo_vol_cible(_equity(calme), 0.15, 20) == 1.0


def test_desactive_par_defaut_le_comportement_est_NEUTRE():
    """`vol_cible = 0` doit renvoyer exactement 1,0 : la porte VIX décide seule."""
    import numpy as np
    agite = list(np.random.default_rng(1).normal(0.0, 0.05, 60))
    assert _expo_vol_cible(_equity(agite), 0.0, 20) == 1.0


def test_un_historique_trop_court_est_NEUTRE_et_non_zero():
    """Renvoyer 0 en début de backtest supprimerait les premières semaines de trading —
    un biais silencieux. On renvoie 1,0 : neutre."""
    for n in (0, 1, 5, 9):
        assert _expo_vol_cible(_equity([0.01] * n), 0.15, 20) == 1.0


def test_une_equity_PLATE_ne_divise_pas_par_zero():
    assert _expo_vol_cible(_equity([0.0] * 40), 0.15, 20) == 1.0


def test_l_exposition_est_bien_proportionnelle_a_la_CIBLE_sur_la_VOL():
    """Contrôle de la formule : à vol réalisée fixée, doubler la cible double
    l'exposition — tant qu'on reste sous le plafond de 1,0."""
    import numpy as np
    r = list(np.random.default_rng(2).normal(0.0, 0.02, 60))        # ~32 % annualisés
    e10 = _expo_vol_cible(_equity(r), 0.10, 20)
    e20 = _expo_vol_cible(_equity(r), 0.20, 20)
    assert e20 == pytest.approx(2 * e10, rel=1e-9)
    assert e20 < 1.0


def test_le_backtest_complet_accepte_le_parametre_et_reduit_l_exposition():
    """Bout en bout : le paramètre est bien câblé, et l'activer ne peut que réduire."""
    from datetime import UTC, datetime, timedelta

    import numpy as np

    from packages.backtest.fast_swing import fast_swing_backtest
    from packages.core.models import Bar
    rng = np.random.default_rng(3)
    t0 = datetime(2020, 1, 1, tzinfo=UTC)
    data = {}
    for k in range(12):
        px = 100 * np.cumprod(1 + rng.normal(0.0005, 0.02, 400))
        data[f"S{k:02d}"] = [Bar(f"S{k:02d}", "1d", t0 + timedelta(days=i),
                                 float(p), float(p) * 1.01, float(p) * 0.99,
                                 float(p), 1e6) for i, p in enumerate(px)]
    _, j0, eq0, _ = fast_swing_backtest(data, cash=10_000, close_at_end=True)
    _, j1, eq1, _ = fast_swing_backtest(data, cash=10_000, close_at_end=True,
                                        vol_cible=0.10)
    assert len(j1.all()) <= len(j0.all())        # ne peut que réduire l'activité
