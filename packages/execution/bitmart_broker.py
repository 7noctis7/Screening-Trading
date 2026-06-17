"""BitmartBroker — exécution CRYPTO via ccxt (paires /USDC), interface miroir de SimBroker/Alpaca.

Sécurité d'abord : **dry-run par défaut** (aucun ordre réel), clés via .env
(BITMART_API_KEY / BITMART_API_SECRET / BITMART_API_MEMO). `ccxt` n'est importé que si réellement
utilisé → testable sans dépendance ni réseau. Permissions minimales (jamais de retrait).
"""

from __future__ import annotations

import os

from packages.core.models import Order, OrderStatus, Position, Side


def position_from_ccxt(p) -> Position:
    """Position ccxt (dict) → Position interne."""
    qty = abs(float(p.get("contracts") or p.get("amount") or 0.0))
    side = Side.SHORT if str(p.get("side", "long")).lower() == "short" else Side.LONG
    entry = float(p.get("entryPrice") or p.get("average") or 0.0)
    return Position(p.get("symbol", ""), side, qty, entry)


class BitmartBroker:
    name = "bitmart"
    is_paper = False                 # Bitmart n'a pas de vrai paper → dry_run protège

    def __init__(self, api_key: str | None = None, api_secret: str | None = None,
                 memo: str | None = None, dry_run: bool = True) -> None:
        self.dry_run = dry_run
        self._key = api_key or os.environ.get("BITMART_API_KEY", "")
        self._secret = api_secret or os.environ.get("BITMART_API_SECRET", "")
        self._memo = memo or os.environ.get("BITMART_API_MEMO", "")
        self._ex = None              # connexion ccxt paresseuse

    def _client(self):
        if self._ex is None:
            import ccxt  # import local
            self._ex = ccxt.bitmart({"apiKey": self._key, "secret": self._secret,
                                     "uid": self._memo, "enableRateLimit": True})
        return self._ex

    def submit(self, order: Order) -> Order:
        side = "buy" if order.side is Side.LONG else "sell"
        if self.dry_run or not (self._key and self._secret):
            order.status = OrderStatus.SUBMITTED      # simulation : rien n'est envoyé
            return order
        try:
            res = self._client().create_order(order.instrument, "market", side, order.qty)
            order.status = OrderStatus.FILLED if res.get("status") in ("closed", "filled") \
                else OrderStatus.SUBMITTED
        except Exception:  # noqa: BLE001
            order.status = OrderStatus.REJECTED
        return order

    def last_price(self, symbol: str) -> float:
        """Dernier prix (ccxt) pour dimensionner un ordre ; 0.0 si indisponible/dry-run."""
        if self.dry_run or not (self._key and self._secret):
            return 0.0
        try:
            return float(self._client().fetch_ticker(symbol).get("last") or 0.0)
        except Exception:  # noqa: BLE001
            return 0.0

    def positions(self) -> list[Position]:
        if self.dry_run or not (self._key and self._secret):
            return []
        try:
            return [position_from_ccxt(p) for p in self._client().fetch_positions()]
        except Exception:  # noqa: BLE001
            return []

    def equity(self) -> float:
        if self.dry_run or not (self._key and self._secret):
            return 0.0
        try:
            bal = self._client().fetch_balance()
            return float(bal.get("total", {}).get("USDC", 0.0))
        except Exception:  # noqa: BLE001
            return 0.0

    def cancel(self, client_id: str) -> bool:
        return True
