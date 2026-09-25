"""Le budget crypto ne se réserve qu'à de la crypto NÉGOCIABLE (constaté sur le VPS, 25/09).

`crypto_weights` retenait toute paire contenant « /USD » — GBP/USD, AUD/USD, NZD/USD, du
FOREX. Le routage les écartait ensuite (« crypto hors whitelist Alpaca »), mais `repartir`
leur avait déjà réservé 15 % du compte : QQQ tombait de 50 % à 42,5 % et 15 % restaient en
cash pour une poche vide — `make live` annonçait une vente de 7 905 $ de QQQ pour rien.
"""

from datetime import UTC, datetime, timedelta

import numpy as np

from packages.core.models import Bar


def _serie(sym, graine):
    rng = np.random.default_rng(graine)
    px = 1.2 * np.exp(np.cumsum(rng.normal(0, 0.005, 200)))
    return [Bar(sym, "1d", datetime(2024, 1, 1, tzinfo=UTC) + timedelta(days=i), p, p, p, p, 1e9)
            for i, p in enumerate(px)]


def test_le_forex_n_entre_pas_dans_la_poche_crypto():
    from packages.backtest.crypto_sleeve import crypto_weights
    data = {s: _serie(s, k) for k, s in enumerate(["GBP/USD", "AUD/USD", "NZD/USD", "EUR/USD"])}
    ac = {s: "forex" for s in data}
    assert crypto_weights(data, asset_classes=ac, min_names=2) == {}


def test_crypto_non_negociable_ne_consomme_aucun_budget():
    from packages.portfolio.budget_poches import negociables
    assert negociables({"GBP/USD": 0.5, "XYZ/USD": 0.5}) == {}
    assert negociables({"BTC/USD": 0.6, "GBP/USD": 0.4}) == {"BTC/USD": 0.6}
