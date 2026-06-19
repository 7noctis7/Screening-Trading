"""AlpacaBroker — implémente l'interface Broker (PAPER par défaut). Requiert alpaca-py.

Même interface que SimBroker → parité backtest↔paper↔live (on échange juste le broker).
Le réseau est isolé ; les mappers (`position_from_alpaca`, `is_filled`) sont purs/testés.
Permissions minimales, jamais retrait. Clés via .env (ALPACA_API_KEY / ALPACA_API_SECRET).
"""

from __future__ import annotations

import os

from packages.core.models import Order, OrderStatus, Position, Side

_STATUS = {
    "new": OrderStatus.SUBMITTED, "accepted": OrderStatus.SUBMITTED,
    "partially_filled": OrderStatus.PARTIALLY_FILLED, "filled": OrderStatus.FILLED,
    "canceled": OrderStatus.CANCELLED, "rejected": OrderStatus.REJECTED,
}


def position_from_alpaca(p) -> Position:
    """Objet position Alpaca (duck-typed) → Position interne."""
    qty = abs(float(p.qty))
    side = Side.LONG if str(getattr(p, "side", "long")).lower().endswith("long") else Side.SHORT
    return Position(p.symbol, side, qty, float(p.avg_entry_price))


def order_status_from_alpaca(o) -> OrderStatus:
    return _STATUS.get(str(getattr(o, "status", "")).lower(), OrderStatus.PENDING)


class AlpacaBroker:
    name = "alpaca"
    is_paper = True

    def __init__(self, api_key: str | None = None, api_secret: str | None = None,
                 paper: bool = True) -> None:
        self.is_paper = paper
        from alpaca.trading.client import TradingClient  # import local
        self._client = TradingClient(
            api_key or os.environ.get("ALPACA_API_KEY", ""),
            api_secret or os.environ.get("ALPACA_API_SECRET", ""),
            paper=paper)

    def submit(self, order: Order) -> Order:
        from alpaca.trading.requests import MarketOrderRequest
        from alpaca.trading.enums import OrderSide, TimeInForce
        req = MarketOrderRequest(
            symbol=order.instrument, qty=order.qty,
            side=OrderSide.BUY if order.side is Side.LONG else OrderSide.SELL,
            time_in_force=TimeInForce.DAY,
            client_order_id=order.client_id)  # idempotence native Alpaca
        res = self._client.submit_order(req)
        order.status = order_status_from_alpaca(res)
        return order

    def submit_notional(self, symbol: str, side: Side, notional: float):
        """Ordre marché par MONTANT $ (Alpaca gère le fractionnement) — pratique pour répliquer
        une allocation cible en %. Reste en paper si paper=True."""
        from alpaca.trading.requests import MarketOrderRequest
        from alpaca.trading.enums import OrderSide, TimeInForce
        req = MarketOrderRequest(
            symbol=symbol, notional=round(notional, 2),
            side=OrderSide.BUY if side is Side.LONG else OrderSide.SELL,
            time_in_force=TimeInForce.DAY)
        return self._client.submit_order(req)

    def positions(self) -> list[Position]:
        return [position_from_alpaca(p) for p in self._client.get_all_positions()]

    def equity(self) -> float:
        return float(self._client.get_account().equity)

    def portfolio_history(self, period: str = "1A", timeframe: str = "1D") -> list[dict]:
        """Historique RÉEL d'equity du compte (Alpaca le stocke). Renvoie [{t, v}] (vide si indispo)."""
        from datetime import datetime, timezone
        try:
            from alpaca.trading.requests import GetPortfolioHistoryRequest
            ph = self._client.get_portfolio_history(
                GetPortfolioHistoryRequest(period=period, timeframe=timeframe))
            ts, eq = list(ph.timestamp or []), list(ph.equity or [])
            return [{"t": datetime.fromtimestamp(t, tz=timezone.utc).date().isoformat(),
                     "v": round(float(v), 2)} for t, v in zip(ts, eq) if v]
        except Exception:  # noqa: BLE001
            return []

    def cancel(self, client_id: str) -> bool:
        try:
            o = self._client.get_order_by_client_id(client_id)
            self._client.cancel_order_by_id(o.id)
            return True
        except Exception:  # noqa: BLE001
            return False
