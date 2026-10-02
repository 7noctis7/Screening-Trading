"""Moteur de backtest event-driven — keystone du système.

Assemble la chaîne complète via les MÊMES interfaces qu'en live (parité) :
  data → (régime) → stratégie → ordre → risk engine (veto) → sizing → broker
       → gestion stop/target → journal → courbe d'equity.

Multi-instruments sur un broker partagé : exerce aussi le risque portefeuille
(max positions, exposition par actif, kill-switch drawdown quotidien).

Hypothèses : long-only, slippage/frais via CostModel, stop/target testés sur low/high.

TIMING (sprint de justesse du 02/10, audit Phase 0). Le signal se lit sur la barre `t`
CLOSE ; l'ordre s'exécute à l'OUVERTURE de `t+1` (`exec_lag=1`, défaut). L'ancien
moteur remplissait au close de la barre même qui avait produit le signal : il achetait
un prix qu'il venait d'observer, un look-ahead d'une demi-barre qui flattait tout
signal de cassure. Un stop traversé par un GAP se remplit à l'ouverture, pas au stop :
un R peut donc être pire que −1, et c'est la vérité du marché. `exec_lag=0` rétablit
l'ancien comportement, pour comparaison seulement.
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
from packages.execution.fills import charge_du_roundtrip, fill_produit
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
    fill_entree: object = None   # le Fill d'ouverture — porte la commission payée


@dataclass
class BacktestResult:
    equity_curve: list[float] = field(default_factory=list)
    timestamps: list[object] = field(default_factory=list)
    journal: TradeJournal = field(default_factory=TradeJournal)


class BacktestEngine:
    def __init__(self, strategy, sizer, risk_engine: RiskEngine, broker: SimBroker,
                 regime_classifier=None, asset_class: AssetClass = AssetClass.EQUITY,
                 exec_lag: int = 1) -> None:
        if exec_lag not in (0, 1):
            raise ValueError("exec_lag ∈ {0, 1} (1 = ouverture de la barre suivante)")
        self.exec_lag = exec_lag
        # Décisions prises au close de `t`, exécutées à l'ouverture de `t+1`.
        self._pending: dict[str, tuple] = {}
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
        # 0) ce qui a été décidé au close de `t-1` s'exécute à l'ouverture de `t`
        self._executer_en_attente(sym, bar, result)
        # 1) gestion des sorties stop/target sur la position ouverte (y compris celle
        #    ouverte à l'ouverture de cette barre : prudent, le chemin intra-barre est
        #    inconnu)
        if sym in self._open:
            ot = self._open[sym]
            mark = bar.close
            ot.mfe = max(ot.mfe, mark - ot.entry_price)
            ot.mae = min(ot.mae, mark - ot.entry_price)
            sortie = self._sortie_intra_barre(ot, bar)
            if sortie is not None:
                self._close(sym, sortie[0], bar.ts, sortie[1], result)
                return
        # 2) signaux de la stratégie, lus sur la barre CLOSE
        regime = self.regime.classify(window) if self.regime else None
        for sig in self.strategy.generate_signals(window, regime):
            if sig.direction is SignalDirection.FLAT and sym in self._open:
                self._decider(sym, ("close", sig.reason or "signal_exit"), bar, result)
            elif sig.direction is SignalDirection.LONG and sym not in self._open:
                self._decider(sym, ("open", sig, regime), bar, result)

    def _sortie_intra_barre(self, ot: _OpenTrade, bar) -> tuple[float, str] | None:
        """Stop puis objectif (ordre pessimiste). Avec `exec_lag=1`, un stop traversé
        par un gap d'ouverture se remplit à l'OUVERTURE — jamais mieux que le marché."""
        if ot.stop is not None and bar.low <= ot.stop:
            prix = min(ot.stop, bar.open) if self.exec_lag else ot.stop
            return prix, "stop_hit"
        if ot.target is not None and bar.high >= ot.target:
            return ot.target, "target_hit"
        return None

    def _decider(self, sym, action: tuple, bar, result) -> None:
        if self.exec_lag:
            self._pending[sym] = action
        else:
            self._executer(sym, action, bar.close, bar, result)

    def _executer_en_attente(self, sym, bar, result) -> None:
        action = self._pending.pop(sym, None)
        if action is None:
            return
        self.broker.mark(sym, bar.open)              # le prix auquel l'ordre arrive
        self._executer(sym, action, bar.open, bar, result)
        self.broker.mark(sym, bar.close)             # l'equity se lit au close

    def _executer(self, sym, action: tuple, prix: float, bar, result) -> None:
        if action[0] == "close":
            if sym in self._open:
                self._close(sym, prix, bar.ts, action[1], result)
        elif sym not in self._open:
            self._try_open(sym, action[1], bar, action[2], prix)

    def _try_open(self, sym, sig: Signal, bar, regime,
                  prix: float | None = None) -> None:
        prix = bar.close if prix is None else prix
        equity = self.broker.equity()
        qty = self.sizer.size(sig, equity, prix, regime)
        if qty <= 0:
            return
        order = Order(sym, Side.LONG, qty, OrderType.MARKET, limit_price=prix)
        sig.features["ref_price"] = prix
        decision = self.risk.approve(order, self.broker.positions(), equity, regime, sig)
        if not decision.approved:
            return
        before = self.broker.position(sym)
        _n_fills = len(getattr(self.broker, "fills", []))
        self.broker.submit(order)
        pos = self.broker.position(sym)
        if pos is None or pos is before:
            return
        self._open[sym] = _OpenTrade(
            sig, pos.avg_price, qty, bar.ts, sig.stop, sig.target,
            fill_entree=fill_produit(self.broker, _n_fills))

    def _close(self, sym, price, ts, reason, result) -> None:
        ot = self._open.pop(sym, None)
        if ot is None:
            return
        sell_fill = self.broker.costs.apply_sell(price)
        _n_fills = len(getattr(self.broker, "fills", []))
        # Même règle que `fast_swing._close` : le broker encaisse le prix de sortie
        # journalisé, pas la dernière clôture marquée. Sans ce mark, un stop touché
        # créditait le cash au cours de clôture de la barre.
        self.broker.mark(sym, price)
        order = Order(sym, Side.SHORT, ot.qty, OrderType.MARKET, limit_price=price)
        self.broker.submit(order)
        # `pnl_gross` porte l'écart de prix (slippage inclus : il EST dans les prix de
        # fill). `pnl_net` en retranche la commission des deux jambes, et elle seule.
        charge = charge_du_roundtrip(ot.fill_entree,
                                     fill_produit(self.broker, _n_fills))
        pnl = (sell_fill - ot.entry_price) * ot.qty
        net = pnl if charge is None else pnl - charge
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
            features_snapshot=dict(ot.signal.features), fees=charge,
            pnl_gross=pnl, pnl_net=net,
            pnl_pct=net / (ot.entry_price * ot.qty) if ot.qty else 0.0,
            r_multiple=r_mult, is_win=net > 0, mfe=ot.mfe, mae=ot.mae))
