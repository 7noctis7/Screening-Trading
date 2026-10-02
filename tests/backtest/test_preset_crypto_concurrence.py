"""D4 (02/10) : plus de poche crypto obligatoire — la crypto CONCOURT avec les actions.

Décision du propriétaire : pas de réserve fixe pour la crypto, mais une crypto mieux
classée qu'une action doit pouvoir entrer au portefeuille. C'est déjà la règle de la
sélection de production : les paires négociables chez le courtier paper sont dans
l'univers du preset (`routing.is_tradeable`), classées avec les actions sur le même
momentum, puis pondérées par leur risque (ERC) et plafonnées comme toute ligne.
"""

from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from packages.backtest.preset_weights import preset_latest_weights_explique
from packages.execution.routing import is_tradeable
from tests.backtest.test_preset_diag import Bar, _panier

T0 = datetime(2021, 1, 1, tzinfo=UTC)


def _crypto(drift: float, vol: float = 0.03, n: int = 900) -> list:
    px = 100 * np.cumprod(1 + np.random.default_rng(99).normal(drift, vol, n))
    return [Bar(T0 + timedelta(days=j), *(4 * [float(px[j])]), 1e6) for j in range(n)]


def _poids(drift: float) -> dict:
    data = _panier(n_titres=20, seed=1)
    data["BTC/USD"] = _crypto(drift)
    poids, _ = preset_latest_weights_explique(
        data, {}, asset_classes={"BTC/USD": "crypto"}, top_k=12, min_weight=0.025)
    return poids


def test_la_crypto_negociable_est_dans_l_univers_de_production():
    assert is_tradeable("BTC/USD", "crypto") and is_tradeable("ETH/USD", "crypto")
    assert not is_tradeable("ZEC/USDC", "crypto")       # hors liste Alpaca : exclue


def test_une_crypto_mieux_classee_que_les_actions_entre_au_portefeuille():
    poids = _poids(drift=0.004)
    assert poids.get("BTC/USD", 0.0) > 0.0
    assert poids["BTC/USD"] <= 0.10 + 1e-9      # plafond de ligne, comme une action


def test_une_crypto_en_baisse_n_entre_pas():
    assert "BTC/USD" not in _poids(drift=-0.002)


@pytest.mark.parametrize("drift", [0.004, -0.002])
def test_aucune_reserve_le_portefeuille_reste_entierement_alloue(drift):
    assert sum(_poids(drift).values()) == pytest.approx(1.0, abs=1e-3)
