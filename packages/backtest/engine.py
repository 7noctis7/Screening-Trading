"""Moteur de backtest event-driven — keystone du système.

Assemble la chaîne complète via les MÊMES interfaces qu'en live (parité) :
  data → (régime) → stratégie → ordre → risk engine (veto) → sizing → broker
       → gestion stop/target → journal → courbe d'equity.

Multi-instruments sur un broker partagé : exerce aussi le risque portefeuille
(max positions, exposition par actif, kill-switch drawdown quotidien).

Hypothèses v1 (documentées, à raffiner) : long-only, fills immédiats à la clôture
de barre (slippage/frais via CostModel), stop/target testés sur low/high de la barre.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from packages.core.models import (
    AssetClass,
    Order,
    OrderType,
    Side,
    Signal,
    SignalDirection,
    TradeRecord,
)
from packages.execution.sim_broker import SimBroker
from packages.risk.engine import RiskEngine
from packages.storage.journal import TradeJournal


@dataclass(slots=True)
class _OpenTrade:
    signal: Signal
    entry_price: float  # fill net (slippage incluse)
    qty: float
    entry_ts: object
    stop: float | None
    target: float | None
    mfe: float = 0.0
    mae: float = 0.0


@dataclass
class BacktestResult:
    equity_curve: list[float] = field(default_factory=list)
    timestamps: list[object] = field(default_factory=list)
    journal: TradeJournal = field(default_factory=TradeJournal)


class BacktestEngine:
    def __init__(self, strategy, sizer, risk_engine: RiskEngine, broker: SimBroker,
                 regime_classifier=None, asset_class: AssetClass = AssetClass.EQUITY) -> None:
        self.strategy = strategy
        self.sizer = sizer
        self.risk = risk_engine
        self.broker = broker
        self.regime = regime_classifier
        self.asset_class = asset_class
        self._open: dict[str, _OpenTrade] = {}
        self._trade_id = 0

    def run(self, data: dict[str, list]) -> BacktestResult:
        result = BacktestResult(journal=TradeJournal())
        symbols = list(data)
        n = max(len(b) for b in data.values())
        self.risk.new_day(self.broker.equity())
        current_day = None
        for t in range(n):
            day = None
            for sym in symbols:
                bars = data[sym]
                if t >= len(bars):
                    continue
                bar = bars[t]
                day = bar.ts.date()
                self.broker.mark(sym, bar.close)
            if day is not None and day != current_day:
                self.risk.new_day(self.broker.equity())
                current_day = day
            self.risk.mark_equity(self.broker.equity())
            for sym in symbols:
                bars = data[sym]
                if t >= len(bars):
                    continue
                self._step_symbol(sym, bars, t, result)
            result.equity_curve.append(self.broker.equity())
            result.timestamps.append(data[symbols[0]][min(t, len(data[symbols[0]]) - 1)].ts)
        # clôture des positions encore ouvertes en fin de backtest
        for sym in list(self._open):
            self._close(sym, data[sym][-1].close, data[sym][-1].ts, "end_of_backtest", result)
        return result

    def _step_symbol(self, sym, bars, t, result) -> None:
        bar = bars[t]
        window = bars[: t + 1]
        # 1) gestion des sorties stop/target sur la position ouverte
        if sym in self._open:
            ot = self._open[sym]
            mark = bar.close
            ot.mfe = max(ot.mfe, mark - ot.entry_price)
            ot.mae = min(ot.mae, mark - ot.entry_price)
            if ot.stop is not None and bar.low <= ot.stop:
                self._close(sym, ot.stop, bar.ts, "stop_hit", result)
                return
            if ot.target is not None and bar.high >= ot.target:
                self._close(sym, ot.target, bar.ts, "target_hit", result)
                return
        # 2) signaux de la stratégie
        regime = self.regime.classify(window) if self.regime else None
        for sig in self.strategy.generate_signals(window, regime):
            if sig.direction is SignalDirection.FLAT and sym in self._open:
                self._close(sym, bar.close, bar.ts, sig.reason or "signal_exit", result)
            elif sig.direction is SignalDirection.LONG and sym not in self._open:
                self._try_open(sym, sig, bar, regime)

    def _try_open(self, sym, sig: Signal, bar, regime) -> None:
        equity = self.broker.equity()
        qty = self.sizer.size(sig, equity, bar.close, regime)
        if qty <= 0:
            return
        order = Order(sym, Side.LONG, qty, OrderType.MARKET, limit_price=bar.close)
        sig.features["ref_price"] = bar.close
        decision = self.risk.approve(order, self.broker.positions(), equity, regime, sig)
        if not decision.approved:
            return
        before = self.broker.position(sym)
        self.broker.submit(order)
        pos = self.broker.position(sym)
        if pos is None or pos is before:
            return
        self._open[sym] = _OpenTrade(sig, pos.avg_price, qty, bar.ts, sig.stop, sig.target)

    def _close(self, sym, price, ts, reason, result) -> None:
        ot = self._open.pop(sym, None)
        if ot is None:
            return
        sell_fill = self.broker.costs.apply_sell(price)
        order = Order(sym, Side.SHORT, ot.qty, OrderType.MARKET, limit_price=price)
        self.broker.submit(order)
        pnl = (sell_fill - ot.entry_price) * ot.qty
        risk_per_unit = (ot.entry_price - ot.stop) if ot.stop else None
        r_mult = ((sell_fill - ot.entry_price) / risk_per_unit
                  if risk_per_unit and risk_per_unit > 0 else None)
        self._trade_id += 1
        regime_lbl = None
        result.journal.append(TradeRecord(
            id=f"T{self._trade_id:04d}", instrument=sym, asset_class=self.asset_class,
            venue=self.broker.name, side=Side.LONG, qty=ot.qty,
            entry_ts=ot.entry_ts, entry_price=ot.entry_price, avg_price=ot.entry_price,
            exit_ts=ts, exit_price=sell_fill, entry_reason=ot.signal.reason,
            exit_reason=reason, strategy=self.strategy.name, regime=regime_lbl,
            features_snapshot=dict(ot.signal.features),
            pnl_net=pnl, pnl_pct=pnl / (ot.entry_price * ot.qty) if ot.qty else 0.0,
            r_multiple=r_mult, is_win=pnl > 0, mfe=ot.mfe, mae=ot.mae))
