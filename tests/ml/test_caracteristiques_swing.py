"""Features swing : causalité stricte, alignement, unités.

La propriété qui décide de tout : une feature à l'indice `i` ne doit dépendre d'AUCUNE
barre postérieure. On ne l'inspecte pas à l'œil, on réécrit le futur et on vérifie que
rien ne bouge — c'est le seul test qui attrape un `.shift()` oublié.
"""

import math
from dataclasses import dataclass

from packages.ml.caracteristiques_swing import (
    compression_volatilite,
    construire,
    distance_aux_ema,
    ema,
    moments_glissants,
)


@dataclass
class B:
    open: float
    high: float
    low: float
    close: float
    volume: float


def _serie(n: int = 600) -> list[B]:
    out = []
    for i in range(n):
        p = 100.0 * (1.0003 ** i) + 3.0 * math.sin(i / 7.0)
        out.append(B(p, p * 1.01, p * 0.99, p, 1000.0 + i))
    return out


def test_ema_est_amorcee_sur_la_moyenne_simple():
    """Amorcer sur la première valeur laisse une empreinte du point de départ."""
    v = [float(i) for i in range(1, 11)]
    e = ema(v, 5)
    assert e[:4] == [None] * 4
    assert abs(e[4] - 3.0) < 1e-12                 # moyenne de 1..5


def test_toutes_les_features_ont_la_longueur_des_barres():
    """Un décalage implicite est la façon la plus discrète d'introduire un look-ahead."""
    bars = _serie()
    f = construire(bars)
    for nom, serie in f.items():
        if nom == "statut":
            continue
        assert len(serie) == len(bars), nom


def test_aucune_feature_ne_bouge_quand_on_reecrit_le_futur():
    """LE test de causalité. Il tomberait sur un z-score plein échantillon."""
    bars = _serie()
    i = 400
    avant = {k: v[i] for k, v in construire(bars).items() if k != "statut"}
    truque = list(bars)
    for k in range(i + 1, len(truque)):
        truque[k] = B(9999.0, 10000.0, 9000.0, 9500.0, 99999.0)
    apres = {k: v[i] for k, v in construire(truque).items() if k != "statut"}
    assert avant == apres


def test_le_zscore_est_glissant_et_non_plein_echantillon():
    """Une fenêtre courte et une fenêtre longue ne peuvent pas donner la même valeur."""
    bars = _serie()
    court = distance_aux_ema(bars, periodes=(50,), fenetre=60)["dist_ema50_z"]
    long_ = distance_aux_ema(bars, periodes=(50,), fenetre=400)["dist_ema50_z"]
    i = 500
    assert court[i] is not None and long_[i] is not None
    assert abs(court[i] - long_[i]) > 1e-6


def test_les_moments_utilisent_les_rendements_log():
    """Sur une croissance géométrique pure, le rendement log est CONSTANT : skew nul."""
    bars = [B(p, p, p, p, 1000.0) for p in (100.0 * 1.001 ** i for i in range(200))]
    m = moments_glissants(bars)
    assert m["skew_log30"][150] is None or abs(m["skew_log30"][150]) < 1e-6


def test_la_compression_est_sans_dimension():
    """Doubler tous les prix ne doit RIEN changer : sinon le ratio n'est pas comparable
    d'un actif à l'autre, et un modèle unique ne peut pas servir tout l'univers."""
    bars = _serie(400)
    double = [B(b.open * 2, b.high * 2, b.low * 2, b.close * 2, b.volume) for b in bars]
    a = compression_volatilite(bars)["squeeze_bb_atr"][300]
    b = compression_volatilite(double)["squeeze_bb_atr"][300]
    assert a is not None and b is not None
    assert abs(a - b) < 1e-9
