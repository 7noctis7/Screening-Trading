"""Backtest swing VECTORISÉ multi-actifs — indicateurs calculés une seule fois.

Même logique économique que `packages/strategies/swing.py` (achat de repli en
tendance, sortie RSI haut / cassure) + sizing vol-target + gardes de risque
(max positions, exposition par actif), mais en **O(n) par actif** au lieu de O(n²) :
on précalcule SMA/RSI/ATR une seule fois puis on déroule le temps une fois. Cela
permet de backtester des CENTAINES d'actifs sur plusieurs années en quelques
secondes. Réutilise SimBroker (comptabilité/parité d'exécution) et produit un
TradeJournal standard.
"""

from __future__ import annotations

import math

from packages.core.models import AssetClass, Order, OrderType, Side, TradeRecord
from packages.execution.costs import CostModel
from packages.execution.sim_broker import SimBroker
from packages.indicators.momentum import RSI
from packages.indicators.trend import SMA
from packages.indicators.volatility import ATR
from packages.storage.journal import TradeJournal

_AC = {e.value: e for e in AssetClass}


def _isnan(v) -> bool:
    return v != v


def fast_swing_backtest(
    data: dict[str, list], *, cash: float = 100_000.0, costs: CostModel | None = None,
    asset_classes: dict[str, str] | None = None, target_annual_vol: float = 0.20,
    max_capital_frac: float = 0.10, max_positions: int = 20, max_pct: float = 0.10,
    trend: int = 50, slope_lookback: int = 5, rsi_period: int = 14, pullback: float = 45.0,
    exit_level: float = 68.0, atr_period: int = 14, atr_stop: float = 2.5, rr: float = 3.0,
    close_at_end: bool = True,
):
    """Retourne (broker, journal, equity_curve, timestamps).

    close_at_end=False laisse les positions ouvertes en fin de fenêtre (utile pour
    afficher les « trades en cours » : elles restent dans broker.positions()).
    """
    costs = costs or CostModel()
    acmap = asset_classes or {}
    symbols = list(data)
    if not symbols:
        return SimBroker(cash=cash, costs=costs), TradeJournal(), [], []
    n = max(len(b) for b in data.values())
    # 1) indicateurs précalculés UNE fois par actif
    sma, rsi, atr = {}, {}, {}
    for s in symbols:
        sma[s] = SMA(trend).compute(data[s])
        rsi[s] = RSI(rsi_period).compute(data[s])
        atr[s] = ATR(atr_period).compute(data[s])
    broker = SimBroker(cash=cash, costs=costs)
    journal = TradeJournal()
    open_t: dict[str, dict] = {}
    equity, ts = [], []
    tid = 0
    frac_cap = min(max_capital_frac, max_pct)
    ref = symbols[0]
    for t in range(n):
        for s in symbols:                                   # mark-to-market
            b = data[s]
            if t < len(b):
                broker.mark(s, b[t].close)
        for s in list(open_t):                              # sorties d'abord
            b = data[s]
            if t >= len(b):
                continue
            bar, ot = b[t], open_t[s]
            ot["mfe"] = max(ot["mfe"], bar.close - ot["entry_price"])
            ot["mae"] = min(ot["mae"], bar.close - ot["entry_price"])
            exit_px = exit_reason = None
            if ot["stop"] is not None and bar.low <= ot["stop"]:
                exit_px, exit_reason = ot["stop"], "stop_hit"
            elif ot["target"] is not None and bar.high >= ot["target"]:
                exit_px, exit_reason = ot["target"], "target_hit"
            else:
                r0, r1, sm = rsi[s][t - 1], rsi[s][t], sma[s][t]
                if not (_isnan(r0) or _isnan(r1) or _isnan(sm)) and \
                        ((r0 >= exit_level > r1) or bar.close < sm):
                    exit_px, exit_reason = bar.close, "RSI haut / cassure tendance"
            if exit_px is not None:
                tid += 1
                _close(broker, journal, s, ot, exit_px, bar.ts, exit_reason, costs, tid,
                       _AC.get(acmap.get(s, "equity"), AssetClass.EQUITY))
                del open_t[s]
        for s in symbols:                                   # entrées
            if s in open_t:
                continue
            if len(open_t) >= max_positions:
                break
            b = data[s]
            if t >= len(b) or t < slope_lookback + 1:
                continue
            j = t - slope_lookback
            sm, smj, r0, r1, a = sma[s][t], sma[s][j], rsi[s][t - 1], rsi[s][t], atr[s][t]
            if any(_isnan(v) for v in (sm, smj, r0, r1, a)):
                continue
            bar = b[t]
            price = bar.close
            if not (price > sm and sm > smj and r0 < pullback <= r1):  # tendance + repli
                continue
            inst_vol = (a / price) * math.sqrt(252) if price > 0 else 0.0
            if inst_vol <= 0:
                continue
            qty = broker.equity() * min(frac_cap, target_annual_vol / inst_vol) / price
            if qty <= 0:
                continue
            before = broker.position(s)
            broker.submit(Order(s, Side.LONG, qty, OrderType.MARKET, limit_price=price))
            pos = broker.position(s)
            if pos is None or pos is before:
                continue
            open_t[s] = {"entry_price": pos.avg_price, "qty": qty, "entry_ts": bar.ts,
                         "stop": price - atr_stop * a, "target": price + rr * atr_stop * a,
                         "reason": "pullback en tendance", "mfe": 0.0, "mae": 0.0,
                         "features": {"sma": sm, "rsi": r1, "atr": a, "ref_price": price}}
        equity.append(broker.equity())
        ts.append(data[ref][min(t, len(data[ref]) - 1)].ts)
    if close_at_end:                                        # clôture en fin de backtest
        for s in list(open_t):
            b = data[s]
            tid += 1
            _close(broker, journal, s, open_t[s], b[-1].close, b[-1].ts, "end_of_backtest",
                   costs, tid, _AC.get(acmap.get(s, "equity"), AssetClass.EQUITY))
    return broker, journal, equity, ts


def _close(broker, journal, sym, ot, price, ts, reason, costs, tid, ac) -> None:
    sell_fill = costs.apply_sell(price)
    broker.submit(Order(sym, Side.SHORT, ot["qty"], OrderType.MARKET, limit_price=price))
    pnl = (sell_fill - ot["entry_price"]) * ot["qty"]
    rpu = (ot["entry_price"] - ot["stop"]) if ot["stop"] else None
    r_mult = ((sell_fill - ot["entry_price"]) / rpu) if rpu and rpu > 0 else None
    journal.append(TradeRecord(
        id=f"T{tid:04d}", instrument=sym, asset_class=ac, venue=broker.name, side=Side.LONG,
        qty=ot["qty"], entry_ts=ot["entry_ts"], entry_price=ot["entry_price"],
        avg_price=ot["entry_price"], exit_ts=ts, exit_price=sell_fill,
        entry_reason=ot["reason"], exit_reason=reason, strategy="swing",
        features_snapshot=dict(ot["features"]), pnl_net=pnl,
        pnl_pct=pnl / (ot["entry_price"] * ot["qty"]) if ot["qty"] else 0.0,
        r_multiple=r_mult, is_win=pnl > 0, mfe=ot["mfe"], mae=ot["mae"]))
