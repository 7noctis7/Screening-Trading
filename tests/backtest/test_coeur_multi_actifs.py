"""Cœur multi-actifs : alignement, absence de look-ahead, coûts réellement chargés.

Ce banc décide s'il faut remplacer le cœur QQQ de production. Trois façons de le faire
mentir, toutes déjà rencontrées dans ce dépôt, et donc toutes testées ici :
  · empiler les séries par POSITION au lieu de les aligner par DATE ;
  · combler un trou avec la clôture SUIVANTE (lire le futur) ;
  · pondérer avec une volatilité calculée sur des données pas encore connues.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from packages.backtest.coeur_multi_actifs import (
    _poids_inverse_vol,
    _rho,
    coeur_equity,
    correlations,
    depart_commun,
    serie_sur_axe,
)


@dataclass
class B:
    ts: datetime
    close: float


def _jours(n: int, depart: str = "2020-01-01") -> list[str]:
    d0 = datetime.fromisoformat(depart).replace(tzinfo=UTC)
    return [(d0 + timedelta(days=i)).date().isoformat() for i in range(n)]


def _barres(axe: list[str], closes: list[float]) -> list[B]:
    return [B(datetime.fromisoformat(j).replace(tzinfo=UTC), c)
            for j, c in zip(axe, closes, strict=True)]


def test_serie_sur_axe_reporte_en_avant_jamais_en_arriere():
    """Avant la première barre : None. Après un trou : la DERNIÈRE clôture connue."""
    axe = _jours(6)
    bars = _barres([axe[2], axe[4]], [100.0, 110.0])
    out = serie_sur_axe(bars, axe)
    assert out[:2] == [None, None]           # le titre n'existait pas : surtout pas 100
    assert out[2] == 100.0
    assert out[3] == 100.0                   # trou comblé par le PASSÉ
    assert out[4] == 110.0
    assert out[5] == 110.0


def test_serie_sur_axe_ignore_l_ordre_des_barres():
    """Des barres désordonnées ne doivent pas produire une série désordonnée."""
    axe = _jours(4)
    bars = _barres([axe[3], axe[1]], [130.0, 110.0])[::-1]
    assert serie_sur_axe(bars, axe) == [None, 110.0, 110.0, 130.0]


def test_depart_commun_attend_la_derniere_composante():
    series = {"A": [1.0, 2.0, 3.0, 4.0], "B": [None, None, 5.0, 6.0]}
    assert depart_commun(series) == 2
    assert depart_commun({"A": [None, None], "B": [1.0, 2.0]}) == -1


def test_un_seul_actif_a_100pct_reproduit_exactement_sa_courbe():
    """Contrôle intégré : un panier à une ligne EST cette ligne, aux coûts près."""
    n = 300
    serie = [100.0 * (1.01 ** i) for i in range(n)]
    r = coeur_equity({"A": serie}, {"A": 1.0}, cout_bps=0.0)
    assert r["available"]
    eq = [x for x in r["equity"] if x is not None]
    assert abs(eq[-1] / eq[0] - serie[-1] / serie[0]) < 1e-6


def test_les_couts_de_reequilibrage_sont_reellement_charges():
    """Sans cette dépense, le cœur multi-actifs partirait avec un avantage inventé."""
    n = 400
    a = [100.0 * (1.005 ** i) for i in range(n)]
    b = [100.0 * (1.002 ** i) for i in range(n)]
    poids = {"A": 0.5, "B": 0.5}
    gratuit = coeur_equity({"A": a, "B": b}, poids, cout_bps=0.0)["equity"][-1]
    charge = coeur_equity({"A": a, "B": b}, poids, cout_bps=25.0)["equity"][-1]
    assert charge < gratuit


def test_inverse_vol_n_utilise_aucune_donnee_posterieure_a_t():
    """LE test de look-ahead : réécrire le FUTUR ne doit RIEN changer aux poids à t.

    Une fenêtre `[t-63:t]` mal bornée (`[t-63:t+1]`, ou un `.rolling()` non décalé) fait
    passer ce test au rouge — c'est exactement ce qu'on veut qu'il attrape.
    """
    n, t = 200, 120
    rends = {"A": [0.001] * n, "B": [0.002 * (-1) ** i for i in range(n)]}
    avant = _poids_inverse_vol(rends, t)
    for s in rends:
        for i in range(t, n):
            rends[s][i] = 99.0                   # futur rendu absurde
    assert _poids_inverse_vol(rends, t) == avant


def test_inverse_vol_pondere_davantage_le_moins_volatil():
    n, t = 200, 120
    calme = [0.001 * (-1) ** i for i in range(n)]
    agite = [0.010 * (-1) ** i for i in range(n)]
    w = _poids_inverse_vol({"calme": calme, "agite": agite}, t)
    assert w["calme"] > w["agite"]
    assert abs(sum(w.values()) - 1.0) < 1e-9


def test_correlation_d_une_serie_et_de_son_oppose_vaut_moins_un():
    n = 300
    hausse = [100.0]
    baisse = [100.0]
    for i in range(1, n):
        r = 0.01 * (-1) ** i + 0.002
        hausse.append(hausse[-1] * (1 + r))
        baisse.append(baisse[-1] * (1 - r))
    rho = correlations({"H": hausse, "B": baisse}, 0)
    assert abs(rho["B/H"] + 1.0) < 1e-6


def test_rho_refuse_des_series_de_longueurs_differentes():
    """Recadrer en silence sur `[-m:]` est la source de trois bugs d'empilement ici."""
    assert _rho([0.01] * 100, [0.01] * 80) == 0.0
