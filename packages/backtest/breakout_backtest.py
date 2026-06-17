"""Backtest de CASSURES (Donchian) + measure rule (Bulkowski) — event study, point-in-time.

Inspiré de Bulkowski : sur une cassure de range (close > plus-haut des N derniers jours), on entre
à J+1, objectif = **measure rule** (hauteur du range projetée), stop = bas du range, sortie max à
J+hold. On mesure l'edge réel (rendement moyen, win rate, **t-stat**, edge vs marché) — sans
complaisance. À n'intégrer QUE si t-stat > 2 et edge vs marché > 0. Numpy pur, testable.
"""

from __future__ import annotations

import numpy as np


def breakout_backtest(data: dict, lookback: int = 20, hold: int = 21,
                      atr_stop: bool = True) -> dict:
    """Event study des cassures Donchian avec measure rule. `data`: {sym: bars(.high/.low/.close)}."""
    ev, mkt = [], []
    wins_target = wins_stop = 0
    for _sym, bars in data.items():
        if not bars or len(bars) < lookback + hold + 2:
            continue
        hi = [b.high for b in bars]
        lo = [b.low for b in bars]
        cl = [b.close for b in bars]
        for t in range(lookback, len(cl) - hold - 1):
            chan_high = max(hi[t - lookback:t])
            chan_low = min(lo[t - lookback:t])
            if not (cl[t] > chan_high and cl[t - 1] <= chan_high):    # cassure haussière confirmée
                continue
            entry = cl[t + 1]
            if entry <= 0:
                continue
            height = chan_high - chan_low
            target = entry + height                                  # measure rule
            stop = chan_low
            exit_px = cl[min(t + 1 + hold, len(cl) - 1)]             # défaut : sortie à J+hold
            for j in range(t + 2, min(t + 1 + hold, len(cl))):
                if lo[j] <= stop:
                    exit_px = stop; wins_stop += 1; break
                if hi[j] >= target:
                    exit_px = target; wins_target += 1; break
            ev.append(exit_px / entry - 1)
            mkt.append(cl[min(t + 1 + hold, len(cl) - 1)] / entry - 1)
    n = len(ev)
    if n < 20:
        return {"available": False, "n_events": n}
    a = np.asarray(ev)
    mean, sd = float(a.mean()), float(a.std())
    return {"available": True, "n_events": n, "lookback": lookback, "hold": hold,
            "mean_return": round(mean, 4), "win_rate": round(float((a > 0).mean()), 4),
            "t_stat": round(mean / sd * np.sqrt(n), 2) if sd else 0.0,
            "target_hits": wins_target, "stop_hits": wins_stop,
            "market_mean_return": round(float(np.mean(mkt)), 4),
            "edge_vs_market": round(mean - float(np.mean(mkt)), 4)}
