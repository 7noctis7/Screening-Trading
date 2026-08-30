"""Backtest causal price-action : sorties partielles et coûts explicites."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from packages.core.models import Bar, Signal, SignalDirection
from packages.execution.costs import CostModel


@dataclass(frozen=True, slots=True)
class PriceActionTrade:
    entry_index: int
    exit_index: int
    direction: int
    quantity: float
    pnl_net: float
    r_multiple: float
    exit_reason: str


@dataclass(frozen=True, slots=True)
class PriceActionStats:
    trades: tuple[PriceActionTrade, ...]
    final_equity: float
    win_rate: float | None
    average_win_r: float | None
    average_loss_r: float | None
    expectancy_r: float | None
    status: str


@dataclass(slots=True)
class _Open:
    entry_index: int
    direction: int
    entry: float
    stop: float
    tp1: float
    tp2: float
    qty: float
    initial_risk: float
    remaining: float
    pnl: float = 0.0
    tp1_done: bool = False


def _fill(price: float, direction: int, opening: bool, costs: CostModel) -> float:
    buy = (direction == 1) == opening
    return costs.apply_buy(price) if buy else costs.apply_sell(price)


def _quantity(
    equity: float,
    risk_fraction: float,
    entry: float,
    stop: float,
    direction: int,
    costs: CostModel,
) -> tuple[float, float]:
    stop_fill = _fill(stop, direction, False, costs)
    price_loss = max(0.0, -direction * (stop_fill - entry))
    fee_per_unit = (entry + stop_fill) * costs.fee_bps / 1e4
    total = price_loss + fee_per_unit
    return ((equity * risk_fraction) / total if total > 0 else 0.0, total)


def _open_trade(
    signal: Signal,
    bar: Bar,
    index: int,
    equity: float,
    risk_fraction: float,
    costs: CostModel,
) -> _Open | None:
    direction = 1 if signal.direction is SignalDirection.LONG else -1
    if signal.stop is None or direction * (bar.open - signal.stop) <= 0:
        return None
    entry = _fill(bar.open, direction, True, costs)
    qty, unit_risk = _quantity(
        equity, risk_fraction, entry, signal.stop, direction, costs
    )
    if qty <= 0:
        return None
    distance = abs(entry - signal.stop)
    tp1 = float(signal.features.get("tp1", entry + direction * 2 * distance))
    if direction * (tp1 - entry) < 2.0 * distance:
        return None
    planned_risk = float(signal.features.get("risk_per_unit", distance))
    planned_tp2 = float(signal.features.get("tp2", entry + direction * 3 * distance))
    planned_entry = float(signal.features.get("entry", entry))
    rr = abs(planned_tp2 - planned_entry) / planned_risk if planned_risk > 0 else 3.0
    tp2 = entry + direction * rr * distance
    return _Open(
        index, direction, entry, signal.stop, tp1, tp2, qty, qty * unit_risk, qty
    )


def _crossed(bar: Bar, level: float, direction: int, favorable: bool) -> bool:
    if (direction == 1) == favorable:
        return bar.high >= level
    return bar.low <= level


def _realize(position: _Open, price: float, qty: float, costs: CostModel) -> None:
    fill = _fill(price, position.direction, False, costs)
    gross = position.direction * (fill - position.entry) * qty
    fees = costs.fee(position.entry * qty) + costs.fee(fill * qty)
    position.pnl += gross - fees
    position.remaining -= qty


def _manage(position: _Open, bar: Bar, costs: CostModel) -> str | None:
    # Stop et objectif dans la même barre : hypothèse pessimiste, stop d'abord.
    if _crossed(bar, position.stop, position.direction, False):
        _realize(position, position.stop, position.remaining, costs)
        return "stop"
    if not position.tp1_done and _crossed(bar, position.tp1, position.direction, True):
        _realize(position, position.tp1, position.qty / 2.0, costs)
        position.tp1_done = True
    if _crossed(bar, position.tp2, position.direction, True):
        _realize(position, position.tp2, position.remaining, costs)
        return "tp2"
    return None


def _stats(trades: list[PriceActionTrade], equity: float) -> PriceActionStats:
    if not trades:
        return PriceActionStats((), equity, None, None, None, None, "UNCALIBRATED")
    wins = [t.r_multiple for t in trades if t.r_multiple > 0]
    losses = [-t.r_multiple for t in trades if t.r_multiple <= 0]
    win_rate = len(wins) / len(trades)
    avg_win = sum(wins) / len(wins) if wins else 0.0
    avg_loss = sum(losses) / len(losses) if losses else 0.0
    expectancy = win_rate * avg_win - (1.0 - win_rate) * avg_loss
    status = "CALIBRATED" if len(trades) >= 30 else "UNCALIBRATED"
    return PriceActionStats(
        tuple(trades), equity, win_rate, avg_win, avg_loss, expectancy, status
    )


def _outcome(position: _Open, index: int, reason: str) -> PriceActionTrade:
    return PriceActionTrade(
        position.entry_index,
        index,
        position.direction,
        position.qty,
        position.pnl,
        position.pnl / position.initial_risk,
        reason,
    )


def backtest_price_action(
    bars: Sequence[Bar],
    strategy,
    initial_equity: float,
    risk_fraction: float,
    costs: CostModel,
) -> PriceActionStats:
    """Signale à la clôture t, exécute à l'ouverture t+1; jamais sur la même barre."""
    if initial_equity <= 0 or not 0 < risk_fraction <= 0.01:
        raise ValueError("capital positif et risque par trade dans ]0, 1%] requis")
    equity, pending, position = initial_equity, None, None
    trades: list[PriceActionTrade] = []
    for i, bar in enumerate(bars):
        if pending is not None and position is None:
            position = _open_trade(pending, bar, i, equity, risk_fraction, costs)
            pending = None
        if position is not None:
            reason = _manage(position, bar, costs)
            if reason:
                equity += position.pnl
                trades.append(_outcome(position, i, reason))
                position = None
        if position is None and pending is None and i + 1 < len(bars):
            signals = strategy.generate_signals(bars[: i + 1])
            pending = signals[0] if signals else None
    if position is not None:
        _realize(position, bars[-1].close, position.remaining, costs)
        equity += position.pnl
        trades.append(_outcome(position, len(bars) - 1, "end"))
    return _stats(trades, equity)
