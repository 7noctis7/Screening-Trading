"""BinanceBroker — faux exchange, sans réseau : idempotence + coût d'achat + dry-run."""
from packages.core.models import Order, OrderStatus, Side
from packages.execution.binance_broker import BinanceBroker


class _Fake:
    def __init__(self):
        self.calls = []

    def fetch_ticker(self, symbol):
        return {"last": 100.0}

    def amount_to_precision(self, symbol, qty):
        return round(qty, 6)

    def market(self, symbol):
        return {"limits": {"cost": {"min": 5.0}}}

    def create_order(self, symbol, type, side, amount, price=None, params=None):  # noqa: A002
        # Régression : un ACHAT marché DOIT porter un prix (coût requis chez Binance/ccxt).
        assert side != "buy" or price, "achat marché sans prix = bug coût"
        self.calls.append((symbol, side, amount, params or {}))
        return {"status": "closed", "filled": amount}


def _broker() -> BinanceBroker:
    b = BinanceBroker(api_key="k", api_secret="s", dry_run=False, testnet=True)
    b._ex = _Fake()
    b._loaded = True
    return b


def test_dry_run_sends_nothing():
    b = BinanceBroker(dry_run=True)
    o = b.submit(Order("BTC/USDT", Side.LONG, 0.1, client_id="c1"))
    assert o.status is OrderStatus.SUBMITTED and b._ex is None   # aucun client créé


def test_idempotent_replay_no_duplicate():
    b = _broker()
    o1 = b.submit(Order("BTC/USDT", Side.LONG, 0.1, client_id="c1"))
    o2 = b.submit(Order("BTC/USDT", Side.LONG, 0.1, client_id="c1"))   # retry même client_id
    assert o1.status is OrderStatus.FILLED and o2.status is OrderStatus.FILLED
    assert len(b._ex.calls) == 1                                  # UN seul ordre net
    assert b._ex.calls[0][3].get("newClientOrderId") == "c1"      # dédup côté exchange


def test_notional_buy_and_min_cost():
    b = _broker()
    o = b.submit_notional("ETH/USDT", Side.LONG, 250.0)
    assert o.status is OrderStatus.FILLED and abs(o.qty - 2.5) < 1e-9   # 250$/100
    r = b.submit_notional("ETH/USDT", Side.LONG, 3.0)             # sous le min notionnel
    assert r.status is OrderStatus.REJECTED and len(b._ex.calls) == 1


def test_testnet_flag_is_paper():
    assert BinanceBroker(dry_run=True, testnet=True).is_paper is True
    assert BinanceBroker(dry_run=True, testnet=False).is_paper is False
