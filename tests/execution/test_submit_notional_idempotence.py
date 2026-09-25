"""QML-006 — l'idempotence doit couvrir le chemin RÉEL : `submit_notional` sous `retry`.

`run_live` n'appelle jamais `submit()` : il appelle `retry(lambda: broker.submit_notional(...),
attempts=3)`. Or `submit_notional` ne portait AUCUN identifiant client — ni chez Alpaca
(`client_order_id`), ni chez Bitmart/Binance (`Order(..., None)`). Un envoi accepté par le
courtier puis perdu en route (timeout) était renvoyé : un ordre DOUBLÉ. La fermeture de
« P0-SI-LIVE #4 » ne testait que `submit()`, un chemin que la production n'emprunte pas.
"""

from __future__ import annotations

import pytest

from packages.common.retry import retry
from packages.core.models import OrderStatus, Side

# --------------------------------------------------------------------------- Alpaca


class _ClientAlpaca:
    """Accepte l'ordre, puis perd la réponse (timeout) ; refuse ensuite un id déjà vu."""

    def __init__(self) -> None:
        self.ordres: dict[str, object] = {}
        self.envois = 0

    def submit_order(self, req):
        self.envois += 1
        cid = req.client_order_id
        if cid in self.ordres:
            raise RuntimeError("client_order_id must be unique")
        self.ordres[cid] = type("O", (), {"id": f"srv-{len(self.ordres)}",
                                          "client_order_id": cid})()
        if self.envois == 1:
            raise TimeoutError("réponse perdue APRÈS acceptation")
        return self.ordres[cid]

    def get_order_by_client_id(self, cid):
        if cid not in self.ordres:
            raise LookupError(cid)
        return self.ordres[cid]


def _alpaca(client):
    from packages.execution.alpaca_broker import AlpacaBroker
    b = AlpacaBroker.__new__(AlpacaBroker)
    b._client, b.is_paper = client, True
    return b


def test_alpaca_un_timeout_apres_acceptation_ne_double_pas_l_ordre():
    pytest.importorskip("alpaca")
    client = _ClientAlpaca()
    b = _alpaca(client)
    res = retry(lambda: b.submit_notional("AAPL", Side.LONG, 1000.0, client_id="qt-1"),
                attempts=3, sleep=lambda _s: None)
    assert len(client.ordres) == 1                 # UN seul ordre chez le courtier
    assert res.client_order_id == "qt-1"           # et c'est lui qu'on rend


def test_alpaca_sans_ordre_chez_le_courtier_l_erreur_remonte():
    pytest.importorskip("alpaca")

    class _Muet(_ClientAlpaca):
        def submit_order(self, req):
            raise ConnectionError("rien n'est parti")
    with pytest.raises(ConnectionError):
        _alpaca(_Muet()).submit_notional("AAPL", Side.LONG, 1000.0, client_id="qt-2")


# --------------------------------------------------------------------------- crypto


class _Exchange:
    def __init__(self) -> None:
        self.appels: list[dict] = []

    def load_markets(self):
        return {}

    def market(self, symbol):
        return {"precision": {"amount": 6}, "limits": {"cost": {"min": 1.0}}}

    def amount_to_precision(self, symbol, amount):
        return f"{amount:.6f}"

    def fetch_ticker(self, symbol):
        return {"last": 100.0}

    def create_order(self, symbol, type, side, amount, price=None, params=None):  # noqa: A002
        self.appels.append({"side": side, "amount": amount, "price": price,
                            "params": params or {}})
        return {"status": "closed", "filled": amount, "amount": amount}


def _crypto(cls):
    b = cls(api_key="k", api_secret="s", dry_run=False) if cls.__name__ == "BinanceBroker" \
        else cls(api_key="k", api_secret="s", memo="m", dry_run=False)
    ex = _Exchange()
    b._client = lambda: ex
    b._ex = ex
    return b, ex


@pytest.mark.parametrize("nom,cle", [("bitmart", "clientOrderId"),
                                     ("binance", "newClientOrderId")])
def test_crypto_submit_notional_porte_l_id_et_ne_renvoie_pas(nom, cle):
    import importlib
    mod = importlib.import_module(f"packages.execution.{nom}_broker")
    cls = getattr(mod, "BitmartBroker" if nom == "bitmart" else "BinanceBroker")
    b, ex = _crypto(cls)
    o1 = b.submit_notional("BTC/USDT", Side.LONG, 500.0, client_id="qt-3")
    o2 = b.submit_notional("BTC/USDT", Side.LONG, 500.0, client_id="qt-3")   # retry
    assert len(ex.appels) == 1                                # un seul envoi
    assert ex.appels[0]["params"].get(cle) == "qt-3"          # dédup côté exchange
    assert ex.appels[0]["price"] == 100.0                     # achat marché : prix fourni
    assert o1.status == o2.status == OrderStatus.FILLED


# --------------------------------------------------------------------------- run_live


def test_run_live_transmet_un_id_stable_aux_adaptateurs_qui_le_declarent():
    import importlib.util
    spec = importlib.util.spec_from_file_location("rl", "scripts/run_live.py")
    rl = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rl)

    vus = []

    class _Avec:
        def submit_notional(self, sym, side, montant, client_id=None):
            vus.append(client_id)
            raise TimeoutError("perdu")

    class _Sans:                       # faux courtier historique : pas de client_id
        def submit_notional(self, sym, side, montant):
            vus.append("sans")
            return "ok"

    with pytest.raises(TimeoutError):
        retry(lambda: rl._envoyer(_Avec(), "AAPL", Side.LONG, 100.0, "qt-4"),
              attempts=3, sleep=lambda _s: None)
    assert vus == ["qt-4"] * 3                     # le MÊME id à chaque tentative
    assert rl._envoyer(_Sans(), "AAPL", Side.LONG, 100.0, "qt-5") == "ok"
    assert rl.id_client("r1", "AAPL", "acheter") != rl.id_client("r2", "AAPL", "acheter")
    assert len(rl.id_client("x" * 40, "BTCUSD", "alleger")) <= 48
