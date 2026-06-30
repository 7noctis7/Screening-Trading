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
        from packages.common.env import load_env
        load_env()                                   # .env quel que soit le point d'entrée
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

    def positions_detailed(self) -> list[dict]:
        """Positions RÉELLES enrichies (prix courant, valeur de marché, P&L latent) pour l'UI."""
        out = []
        for p in self._client.get_all_positions():
            out.append({
                "symbol": p.symbol, "broker": "Alpaca",
                "side": "long" if str(getattr(p, "side", "long")).lower().endswith("long") else "short",
                "qty": abs(float(p.qty)), "avg_price": float(p.avg_entry_price),
                "price": float(getattr(p, "current_price", 0) or 0),
                "market_value": float(getattr(p, "market_value", 0) or 0),
                "pnl": float(getattr(p, "unrealized_pl", 0) or 0),
                "pnl_pct": float(getattr(p, "unrealized_plpc", 0) or 0)})
        return out

    def orders(self, limit: int = 100) -> list[dict]:
        """Ordres RÉELS exécutés (fills) du compte — pour la page Trades. [] si indispo."""
        try:
            from alpaca.trading.requests import GetOrdersRequest
            from alpaca.trading.enums import QueryOrderStatus
            res = self._client.get_orders(GetOrdersRequest(status=QueryOrderStatus.CLOSED, limit=limit))
            out = []
            for o in res:
                fq = float(getattr(o, "filled_qty", 0) or 0)
                if fq <= 0:                       # on ne garde que les ordres réellement remplis
                    continue
                ts = getattr(o, "filled_at", None) or getattr(o, "submitted_at", None)
                out.append({
                    "symbol": o.symbol, "broker": "Alpaca",
                    "side": str(getattr(o, "side", "")).lower().split(".")[-1],
                    "qty": fq, "price": float(getattr(o, "filled_avg_price", 0) or 0),
                    "notional": fq * float(getattr(o, "filled_avg_price", 0) or 0),
                    "date": ts.isoformat() if ts else "",
                    "status": str(getattr(o, "status", "")).lower().split(".")[-1]})
            return out
        except Exception:  # noqa: BLE001
            return []

    def open_orders(self, limit: int = 100) -> list[dict]:
        """Ordres OUVERTS / en attente d'exécution (non encore remplis) — page Trades.
        Inclut new/accepted/pending_new/held/partially_filled (ex. marché fermé le week-end). [] si indispo."""
        try:
            from alpaca.trading.requests import GetOrdersRequest
            from alpaca.trading.enums import QueryOrderStatus
            res = self._client.get_orders(GetOrdersRequest(status=QueryOrderStatus.OPEN, limit=limit))
            out = []
            for o in res:
                rq = float(getattr(o, "qty", 0) or 0)            # ordre en parts (qty)…
                nv = float(getattr(o, "notional", 0) or 0)       # …ou ordre en MONTANT $ (notional, qty=None)
                fq = float(getattr(o, "filled_qty", 0) or 0)
                lp = getattr(o, "limit_price", None)
                px = float(lp) if lp else float(getattr(o, "filled_avg_price", 0) or 0)
                ts = getattr(o, "submitted_at", None) or getattr(o, "created_at", None)
                # montant : notional explicite si présent, sinon parts × prix (si prix connu)
                amount = nv if nv > 0 else (rq * px if px else 0.0)
                out.append({
                    "symbol": o.symbol, "broker": "Alpaca",
                    "side": str(getattr(o, "side", "")).lower().split(".")[-1],
                    "qty": rq, "filled_qty": fq, "notional_order": nv > 0,
                    "price": px, "order_type": str(getattr(o, "order_type", "")).lower().split(".")[-1],
                    "notional": round(amount, 2),
                    "date": ts.isoformat() if ts else "",
                    "status": str(getattr(o, "status", "")).lower().split(".")[-1]})
            return out
        except Exception:  # noqa: BLE001
            return []

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
