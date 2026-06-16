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


def vix_exposure(v: float) -> float:
    """Multiplicateur d'exposition piloté par le VIX (playbook volatilité).
    VIX < 13 → risk-on (+20%) · 13–20 → neutre · 20–30 → on réduit · > 30 → défensif (coupe le levier)."""
    if v < 13:
        return 1.2
    if v < 20:
        return 1.0
    if v < 30:
        return 0.6
    return 0.3


def fast_swing_backtest(
    data: dict[str, list], *, cash: float = 100_000.0, costs: CostModel | None = None,
    asset_classes: dict[str, str] | None = None, target_annual_vol: float = 0.20,
    max_capital_frac: float = 0.10, max_positions: int = 20, max_pct: float = 0.10,
    trend: int = 50, slope_lookback: int = 5, rsi_period: int = 14, pullback: float = 45.0,
    exit_level: float = 68.0, atr_period: int = 14, atr_stop: float = 2.5, rr: float = 3.0,
    close_at_end: bool = True, vix: list | None = None, exit_trend: int = 100,
    rs_lookback: int = 126, daily_max_loss: float = 0.0, trail_atr: float = 0.0,
    next_open_fills: bool = False,
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
    # 1) indicateurs précalculés UNE fois par actif (MM entrée + MM longue de sortie)
    sma, sma_x, rsi, atr = {}, {}, {}, {}
    for s in symbols:
        sma[s] = SMA(trend).compute(data[s])
        sma_x[s] = SMA(exit_trend).compute(data[s])
        rsi[s] = RSI(rsi_period).compute(data[s])
        atr[s] = ATR(atr_period).compute(data[s])
    broker = SimBroker(cash=cash, costs=costs)
    journal = TradeJournal()
    open_t: dict[str, dict] = {}
    equity, ts = [], []
    tid = 0
    frac_cap = min(max_capital_frac, max_pct)
    ref = symbols[0]
    day, day_start_eq, killed = None, cash, False
    for t in range(n):
        for s in symbols:                                   # mark-to-market
            b = data[s]
            if t < len(b):
                broker.mark(s, b[t].close)
        # KILL-SWITCH journalier : nouvelle journée → on mémorise l'equity d'ouverture
        cur_day = data[ref][min(t, len(data[ref]) - 1)].ts.date()
        if cur_day != day:
            day, day_start_eq, killed = cur_day, broker.equity(), False
        if daily_max_loss > 0 and broker.equity() < day_start_eq * (1 - daily_max_loss):
            killed = True                                   # perte journalière max atteinte → stop entrées
        for s in list(open_t):                              # sorties d'abord
            b = data[s]
            if t >= len(b):
                continue
            bar, ot = b[t], open_t[s]
            ot["mfe"] = max(ot["mfe"], bar.close - ot["entry_price"])
            ot["mae"] = min(ot["mae"], bar.close - ot["entry_price"])
            ot["hh"] = max(ot.get("hh", ot["entry_price"]), bar.high)
            # stop effectif = max(stop initial, trailing stop ATR) → on protège les gains
            eff_stop = ot["stop"]
            if trail_atr > 0 and not _isnan(atr[s][t]):
                eff_stop = max(eff_stop, ot["hh"] - trail_atr * atr[s][t])
            exit_px = exit_reason = None
            if eff_stop is not None and bar.low <= eff_stop:
                exit_px = eff_stop
                exit_reason = "trailing_stop" if eff_stop > ot["stop"] + 1e-9 else "stop_hit"
            elif ot["target"] is not None and bar.high >= ot["target"]:
                exit_px, exit_reason = ot["target"], "target_hit"
            else:
                smx = sma_x[s][t]                            # on laisse courir : sortie SEULEMENT
                if not _isnan(smx) and bar.close < smx:      # sur cassure de la MM longue
                    exit_px, exit_reason = bar.close, "cassure tendance (MM longue)"
            if exit_px is not None:
                tid += 1
                _close(broker, journal, s, ot, exit_px, bar.ts, exit_reason, costs, tid,
                       _AC.get(acmap.get(s, "equity"), AssetClass.EQUITY))
                del open_t[s]
        # ENTRÉES : candidats éligibles classés par CONVICTION, cash alloué aux MEILLEURS.
        if len(open_t) < max_positions and not killed:
            vmult = vix_exposure(vix[t]) if vix and t < len(vix) else 1.0
            cands = []
            for s in symbols:
                if s in open_t:
                    continue
                b = data[s]
                if t >= len(b) or t < slope_lookback + 1:
                    continue
                j = t - slope_lookback
                sm, smj, r0, r1, a = sma[s][t], sma[s][j], rsi[s][t - 1], rsi[s][t], atr[s][t]
                if any(_isnan(v) for v in (sm, smj, r0, r1, a)):
                    continue
                price = b[t].close
                if not (price > sm and sm > smj and r0 < pullback <= r1):   # tendance + repli
                    continue
                # conviction = FORCE RELATIVE 6 mois (capte la tendance/drift → surpondère les
                # leaders) + prime de tendance ; classe les meilleures opportunités.
                rs = price / b[t - rs_lookback].close - 1.0 if t >= rs_lookback else price / sm - 1.0
                conviction = rs + 0.5 * (price / sm - 1.0)
                cands.append((conviction, s, price, a, sm))
            cands.sort(key=lambda c: c[0], reverse=True)
            eq = broker.equity()
            # exposition brute cible pilotée par le VIX (≤ ×1.2 en marché calme, < ×1 en stress)
            allowed_gross = eq * vmult
            gross = sum(ot["qty"] * data[sx][min(t, len(data[sx]) - 1)].close
                        for sx, ot in open_t.items())
            for _conv, s, price, a, sm in cands:
                if len(open_t) >= max_positions:
                    break
                room = allowed_gross - gross
                if room < eq * 0.02:                        # plus de marge d'exposition
                    break
                inst_vol = (a / price) * math.sqrt(252) if price > 0 else 0.0
                if inst_vol <= 0:
                    continue
                # exécution à l'OUVERTURE de la barre suivante (anti look-ahead) si dispo
                b = data[s]
                nxt = min(t + 1, len(b) - 1)
                fillp = b[nxt].open if (next_open_fills and nxt > t) else price
                fill_ts = b[nxt].ts if (next_open_fills and nxt > t) else b[t].ts
                qty = min(eq * min(frac_cap, target_annual_vol / inst_vol), room) / fillp
                if qty * fillp < eq * 0.01:                 # ligne trop petite → on saute
                    continue
                before = broker.position(s)
                broker.mark(s, fillp)                       # fill au prix d'exécution…
                broker.submit(Order(s, Side.LONG, qty, OrderType.MARKET, limit_price=fillp))
                broker.mark(s, b[t].close)                  # …puis on rétablit la clôture (MTM)
                pos = broker.position(s)
                if pos is None or pos is before:
                    continue
                gross += qty * fillp                        # consomme la marge d'exposition
                open_t[s] = {"entry_price": pos.avg_price, "qty": qty, "entry_ts": fill_ts,
                             "stop": fillp - atr_stop * a, "target": fillp + rr * atr_stop * a,
                             "reason": "pullback en tendance (top conviction)",
                             "mfe": 0.0, "mae": 0.0, "hh": fillp,
                             "features": {"sma": sm, "rsi": rsi[s][t], "atr": a, "ref_price": fillp,
                                          "conviction": round(_conv, 4)}}
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
