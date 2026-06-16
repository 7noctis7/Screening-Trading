"""Broker simulé (paper) — implémente l'interface Broker.

Le MÊME broker sert au backtest et au paper-live → parité d'exécution. Fills
immédiats au prix courant ajusté des coûts. Tient cash + positions + equity.
"""

from __future__ import annotations

from packages.core.models import Order, OrderStatus, Position, Side
from packages.execution.costs import CostModel


class SimBroker:
    name = "sim"
    is_paper = True

    def __init__(self, cash: float = 100_000.0, costs: CostModel | None = None) -> None:
        self.cash = cash
        self.costs = costs or CostModel()
        self._positions: dict[str, Position] = {}
        self._last_price: dict[str, float] = {}
        self._seen_client_ids: set[str] = set()  # idempotence des retries
        self.fees_paid = 0.0

    def mark(self, instrument: str, price: float) -> None:
        self._last_price[instrument] = price

    def submit(self, order: Order) -> Order:
        # Idempotence : un retry avec le même client_id ne re-remplit pas.
        if order.client_id and order.client_id in self._seen_client_ids:
            order.status = OrderStatus.FILLED
            return order
        price = self._last_price.get(order.instrument)
        if price is None:
            order.status = OrderStatus.REJECTED
            return order
        if order.side is Side.LONG:
            fill = self.costs.apply_buy(price)
            notional = fill * order.qty
            fee = self.costs.fee(notional)
            self.cash -= notional + fee
            self._open_or_add(order.instrument, Side.LONG, order.qty, fill)
        else:  # vente = clôture d'une position long (v1 : pas de short à découvert)
            fill = self.costs.apply_sell(price)
            notional = fill * order.qty
            fee = self.costs.fee(notional)
            self.cash += notional - fee
            self._reduce(order.instrument, order.qty)
        self.fees_paid += fee
        if order.client_id:
            self._seen_client_ids.add(order.client_id)
        order.status = OrderStatus.FILLED
        return order

    def _open_or_add(self, instrument, side, qty, price) -> None:
        pos = self._positions.get(instrument)
        if pos is None:
            self._positions[instrument] = Position(instrument, side, qty, price)
        else:
            total = pos.qty + qty
            pos.avg_price = (pos.avg_price * pos.qty + price * qty) / total
            pos.qty = total

    def _reduce(self, instrument, qty) -> None:
        pos = self._positions.get(instrument)
        if pos is None:
            return
        pos.qty -= qty
        if pos.qty <= 1e-9:
            del self._positions[instrument]

    def positions(self) -> list[Position]:
        return list(self._positions.values())

    def position(self, instrument: str) -> Position | None:
        return self._positions.get(instrument)

    def equity(self) -> float:
        mtm = sum(p.qty * self._last_price.get(p.instrument, p.avg_price)
                  for p in self._positions.values())
        return self.cash + mtm

    def cancel(self, client_id: str) -> bool:
        return True  # fills immédiats → rien à annuler en sim
