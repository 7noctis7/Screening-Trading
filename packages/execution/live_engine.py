"""Moteur de trading LIVE (paper par défaut) — parité avec le backtest.

Réutilise les MÊMES composants/interfaces que le backtest (Strategy, Sizer,
RiskEngine, Broker, TradeJournal). Différence : il réagit barre par barre (streaming)
au lieu d'itérer l'historique. Donc une stratégie validée en backtest tourne en paper
sans réécriture → parité garantie.

Sécurité : PAPER par défaut, retries idempotents, **kill-switch** vérifié à chaque pas
(drawdown quotidien → blocage des entrées). Réconciliation broker↔interne via `reconcile`.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from packages.core.models import (
    Order,
    OrderStatus,
    OrderType,
    Side,
    Signal,
    SignalDirection,
    TradeRecord,
    AssetClass,
)
from packages.common.event_bus import Topic
from packages.common.logging import get_logger
from packages.execution.retry import submit_with_retries
from packages.risk.engine import RiskEngine
from packages.storage.journal import TradeJournal
from packages.storage.journal_sqlite import SqliteTradeJournal

log = get_logger("execution.live_engine")


def _asset_class_for(sym: str) -> AssetClass:
    """Classe d'actif d'après le symbole : les paires crypto contiennent un '/' (BTC/USD)."""
    return AssetClass.CRYPTO if "/" in (sym or "") else AssetClass.EQUITY


@dataclass(slots=True)
class _Open:
    signal: Signal
    entry_price: float
    qty: float
    entry_ts: object
    stop: float | None
    target: float | None


class LiveTradingEngine:
    def __init__(self, strategy, sizer, risk_engine: RiskEngine, broker,
                 journal=None, regime_classifier=None,
                 retry_attempts: int = 3, bus=None) -> None:
        self.strategy = strategy
        self.sizer = sizer
        self.risk = risk_engine
        self.broker = broker
        # LIVE = persistant par défaut (data/journal.db). Passer un TradeJournal()
        # ou SqliteTradeJournal(":memory:") pour les runs synthétiques/tests.
        self.journal = journal or SqliteTradeJournal()
        self.regime = regime_classifier
        self.retry_attempts = retry_attempts
        self.bus = bus                                  # câblé aux alertes en prod (BLOC 1c)
        self._open: dict[str, _Open] = {}
        self._tid = 0
        self._day = None

    def step(self, windows: dict[str, list]) -> None:
        """Un pas : `windows[symbol]` = historique de barres jusqu'à maintenant (inclus)."""
        for sym, bars in windows.items():
            if bars and hasattr(self.broker, "mark"):
                self.broker.mark(sym, bars[-1].close)   # SimBroker ; no-op réel
        equity = self.broker.equity()
        day = next(iter(windows.values()))[-1].ts.date() if windows else None
        if day is not None and day != self._day:
            self.risk.new_day(equity)
            self._day = day
        self.risk.mark_equity(equity)                   # arme le kill-switch si besoin
        for sym, bars in windows.items():
            if bars:
                self._step_symbol(sym, bars)

    @property
    def kill_switch(self) -> bool:
        return self.risk.kill_switch

    def reconcile(self, internal_positions=None):
        from packages.execution.reconcile import reconcile
        internal = internal_positions or [
            self._as_position(sym, ot) for sym, ot in self._open.items()]
        return reconcile(self.broker.positions(), internal, bus=self.bus)

    # -- interne -----------------------------------------------------------
    def _step_symbol(self, sym, bars) -> None:
        bar = bars[-1]
        if sym in self._open:                           # sorties stop/target
            ot = self._open[sym]
            if ot.stop is not None and bar.low <= ot.stop:
                self._close(sym, ot.stop, bar.ts, "stop_hit"); return
            if ot.target is not None and bar.high >= ot.target:
                self._close(sym, ot.target, bar.ts, "target_hit"); return
        regime = self.regime.classify(bars) if self.regime else None
        for sig in self.strategy.generate_signals(bars, regime):
            if sig.direction is SignalDirection.FLAT and sym in self._open:
                self._close(sym, bar.close, bar.ts, sig.reason or "signal_exit")
            elif sig.direction is SignalDirection.LONG and sym not in self._open:
                self._try_open(sym, sig, bar, regime)

    def _try_open(self, sym, sig: Signal, bar, regime) -> None:
        equity = self.broker.equity()
        qty = self.sizer.size(sig, equity, bar.close, regime)
        if qty <= 0:
            return
        sig.features["ref_price"] = bar.close
        order = Order(sym, Side.LONG, qty, OrderType.MARKET, limit_price=bar.close,
                      client_id=uuid.uuid4().hex)
        if not self.risk.approve(order, self.broker.positions(), equity, regime, sig).approved:
            return
        res = submit_with_retries(self.broker, order, attempts=self.retry_attempts)
        self._record_open(sym, res, sig, bar, qty)

    def _record_open(self, sym, res: Order, sig, bar, qty: float) -> None:
        """Ouvre une position à la qté RÉELLEMENT remplie. Ne jamais supposer un fill plein :
        un PARTIALLY_FILLED sans `filled_qty` connu → aucune position + alerte CRITICAL."""
        if res.status is OrderStatus.FILLED:
            filled = res.filled_qty if res.filled_qty is not None else qty  # plein = plein
            if filled > 0:
                self._open[sym] = _Open(sig, bar.close, filled, bar.ts, sig.stop, sig.target)
            return
        if res.status is OrderStatus.PARTIALLY_FILLED:
            if res.filled_qty is None:
                self._alert_partial_unknown(sym, qty)   # inconnu → NE PAS ouvrir
                return
            if res.filled_qty > 0:
                self._open[sym] = _Open(sig, bar.close, res.filled_qty, bar.ts, sig.stop, sig.target)
                log.warning("fill partiel — reliquat non exécuté", extra={"extra": {
                    "symbol": sym, "filled": res.filled_qty, "requested": qty,
                    "remainder": qty - res.filled_qty}})
            return
        # SUBMITTED / REJECTED / autre → rien ouvert (position seulement sur fill réel)

    def _alert_partial_unknown(self, sym, qty: float) -> None:
        """PARTIALLY_FILLED sans qté remplie connue : position non ouverte, alerte CRITICAL."""
        log.critical("PARTIALLY_FILLED sans filled_qty — position NON ouverte", extra={"extra": {
            "symbol": sym, "requested": qty}})
        if self.bus is not None:
            self.bus.publish(Topic.PARTIAL_FILL_UNKNOWN, {"symbol": sym, "requested": qty})

    def _close(self, sym, price, ts, reason) -> None:
        ot = self._open.pop(sym, None)
        if ot is None:
            return
        order = Order(sym, Side.SHORT, ot.qty, OrderType.MARKET, limit_price=price,
                      client_id=uuid.uuid4().hex)
        submit_with_retries(self.broker, order, attempts=self.retry_attempts)
        pnl = (price - ot.entry_price) * ot.qty
        self._tid += 1
        self.journal.append(TradeRecord(
            id=f"L{self._tid:04d}", instrument=sym, asset_class=_asset_class_for(sym),
            venue=self.broker.name, side=Side.LONG, qty=ot.qty, entry_ts=ot.entry_ts,
            entry_price=ot.entry_price, avg_price=ot.entry_price, exit_ts=ts,
            exit_price=price, entry_reason=ot.signal.reason, exit_reason=reason,
            strategy=self.strategy.name, features_snapshot=dict(ot.signal.features),
            pnl_net=pnl, pnl_pct=pnl / (ot.entry_price * ot.qty) if ot.qty else 0.0,
            is_win=pnl > 0))

    def _as_position(self, sym, ot: _Open):
        from packages.core.models import Position
        return Position(sym, Side.LONG, ot.qty, ot.entry_price)
