"""BinanceBroker — exécution CRYPTO SPOT via ccxt, avec **TESTNET = vrai paper crypto**.

Miroir de `BitmartBroker` (mêmes garde-fous, mêmes pièges déjà résolus) avec deux différences
qui comptent :
  - **Testnet spot officiel** (`QUANT_BINANCE_TESTNET=1` → sandbox ccxt) : contrairement à
    Bitmart, on peut s'entraîner avec de la fausse monnaie — aligné avec l'ère paper (ADR-0032).
  - Pas de memo : clés `BINANCE_API_KEY` / `BINANCE_API_SECRET` seulement.

Sécurité identique : **dry-run par défaut** (aucun ordre), idempotence `_seen` (rejoue le
résultat RÉEL, jamais de FILLED fabriqué), `newClientOrderId` (dédup côté exchange), achat
marché avec PRIX (BitMart/Binance veulent le coût — bug « REJECTED silencieux » déjà payé),
rejets LOGGÉS. Permissions API minimales, jamais de retrait.
"""

from __future__ import annotations

import os

from packages.core.models import Order, OrderStatus, Position, Side

_STABLES = ("USDT", "USDC", "USD", "FDUSD", "BUSD")


def _map_fill(res: dict, req_qty: float) -> tuple[OrderStatus, float | None]:
    """Réponse ccxt → (statut, qté remplie RÉELLE). Jamais de fill plein supposé."""
    st = (res or {}).get("status") or ""
    filled = (res or {}).get("filled")
    filled = float(filled) if filled is not None else None
    if st in ("closed", "filled"):
        return OrderStatus.FILLED, filled if filled is not None else req_qty
    if filled and 0 < filled < req_qty:
        return OrderStatus.PARTIALLY_FILLED, filled
    if st in ("canceled", "cancelled", "rejected", "expired"):
        return OrderStatus.REJECTED, filled
    return OrderStatus.SUBMITTED, filled


class BinanceBroker:
    name = "binance"
    is_paper: bool = False           # le testnet EST le mode paper ; dry_run protège sinon

    def __init__(self, api_key: str | None = None, api_secret: str | None = None,
                 dry_run: bool = True, testnet: bool | None = None) -> None:
        self.dry_run = dry_run
        self._key = api_key or os.environ.get("BINANCE_API_KEY", "")
        self._secret = api_secret or os.environ.get("BINANCE_API_SECRET", "")
        self.testnet = (testnet if testnet is not None
                        else os.environ.get("QUANT_BINANCE_TESTNET", "1") == "1")
        self.is_paper = self.testnet                   # testnet → fausse monnaie = paper honnête
        self._ex = None
        self._loaded = False
        # Idempotence : client_id → (statut, filled_qty) RÉELS du 1er submit (rejoués tels quels).
        self._seen: dict[str, tuple[OrderStatus, float | None]] = {}

    def _live(self) -> bool:
        return not self.dry_run and bool(self._key and self._secret)

    def _client(self):
        if self._ex is None:
            import ccxt
            self._ex = ccxt.binance({"apiKey": self._key, "secret": self._secret,
                                     "enableRateLimit": True,
                                     "options": {"defaultType": "spot"}})
            if self.testnet:
                self._ex.set_sandbox_mode(True)        # testnet.binance.vision (fausse monnaie)
        if not self._loaded:
            try:
                self._ex.load_markets()
                self._loaded = True
            except Exception:  # noqa: BLE001
                pass
        return self._ex

    def _round_qty(self, symbol: str, qty: float) -> float:
        try:
            return float(self._client().amount_to_precision(symbol, qty))
        except Exception:  # noqa: BLE001
            return round(qty, 6)

    def _min_cost(self, symbol: str) -> float:
        try:
            m = self._client().market(symbol)
            return float(((m.get("limits") or {}).get("cost") or {}).get("min") or 5.0)
        except Exception:  # noqa: BLE001
            return 5.0                                  # minimum notionnel Binance spot usuel

    def _remember(self, order: Order) -> Order:
        if order.client_id:
            self._seen[order.client_id] = (order.status, order.filled_qty)
        return order

    def submit(self, order: Order) -> Order:
        # Idempotence : résultat définitif déjà connu → REJOUÉ tel quel (jamais fabriqué).
        if order.client_id and order.client_id in self._seen:
            order.status, order.filled_qty = self._seen[order.client_id]
            return order
        s = "buy" if order.side is Side.LONG else "sell"
        if not self._live():
            order.status = OrderStatus.SUBMITTED       # dry-run : rien envoyé, rien mémorisé
            return order
        qty = self._round_qty(order.instrument, order.qty)
        if qty <= 0:
            order.status = OrderStatus.REJECTED
            return self._remember(order)
        order.qty = qty
        params = {"newClientOrderId": order.client_id} if order.client_id else {}
        try:
            # ACHAT marché spot : prix requis (ccxt calcule le coût) — cf. bug BitMart 06/07.
            price = None
            if s == "buy":
                price = self.last_price(order.instrument) or None
                if price is None:
                    order.status = OrderStatus.REJECTED
                    return self._remember(order)
            res = self._client().create_order(order.instrument, "market", s, qty,
                                              price, params=params)
            order.status, order.filled_qty = _map_fill(res, qty)
        except Exception as e:  # noqa: BLE001
            import logging
            logging.getLogger("execution.binance").warning(
                "submit %s %s rejeté : %s", s, order.instrument, str(e)[:120])
            order.status = OrderStatus.REJECTED
        return self._remember(order)

    def submit_notional(self, symbol: str, side: Side, cost_usdt: float) -> Order:
        """Ordre marché par MONTANT ($) — pratique pour répliquer une allocation cible."""
        order = Order(symbol, side, 0.0, None)
        if not self._live():
            order.status = OrderStatus.SUBMITTED
            return order
        px = self.last_price(symbol)
        if px <= 0 or cost_usdt <= 0 or cost_usdt < self._min_cost(symbol):
            order.status = OrderStatus.REJECTED
            return order
        order.qty = self._round_qty(symbol, cost_usdt / px)
        if order.qty <= 0:
            order.status = OrderStatus.REJECTED
            return order
        return self.submit(order)

    def last_price(self, symbol: str) -> float:
        if not self._live():
            return 0.0
        try:
            return float(self._client().fetch_ticker(symbol).get("last") or 0.0)
        except Exception:  # noqa: BLE001
            return 0.0

    def positions(self) -> list[Position]:
        """Coins SPOT détenus (solde > 0), stables exclues."""
        if not self._live():
            return []
        out: list[Position] = []
        try:
            total = (self._client().fetch_balance().get("total", {}) or {})
            for coin, amt in total.items():
                amt = float(amt or 0.0)
                if coin in _STABLES or amt <= 0:
                    continue
                sym = f"{coin}/USDT"
                out.append(Position(sym, Side.LONG, amt, self.last_price(sym)))
        except Exception:  # noqa: BLE001
            pass
        return out

    def equity(self) -> float:
        """Cash stable + valeur des coins, en USDT. 0.0 hors-ligne (jamais inventé)."""
        if not self._live():
            return 0.0
        eq = 0.0
        try:
            total = (self._client().fetch_balance().get("total", {}) or {})
            for coin, amt in total.items():
                amt = float(amt or 0.0)
                if amt <= 0:
                    continue
                eq += amt if coin in _STABLES else amt * self.last_price(f"{coin}/USDT")
        except Exception:  # noqa: BLE001
            pass
        return round(eq, 2)

    def positions_detailed(self) -> list[dict]:
        """Positions enrichies pour l'UI. PRU inconnu → P&L None (« — »), jamais un faux 0 %."""
        out: list[dict] = []
        for p in self.positions():
            px = self.last_price(p.instrument)
            out.append({"symbol": p.instrument, "broker": "Binance", "side": "long",
                        "qty": p.qty, "avg_price": None, "price": px,
                        "market_value": round(p.qty * px, 2), "pnl": None, "pnl_pct": None})
        return out
