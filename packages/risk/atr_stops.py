"""ATR-based SL/TP + time stop. Stop beyond the noise, never inside it."""
from __future__ import annotations

import pandas as pd


def atr(df: pd.DataFrame, window: int = 14) -> pd.Series:
    """df: columns high, low, close."""
    prev = df["close"].shift(1)
    tr = pd.concat([df["high"] - df["low"], (df["high"] - prev).abs(),
                    (df["low"] - prev).abs()], axis=1).max(axis=1)
    return tr.rolling(window).mean()


def stop_levels(entry: float, atr_val: float, side: str = "long",
                k_sl: float = 2.5, k_tp: float | None = None) -> dict:
    """k_tp=None => no fixed TP (trend-following: trail instead).
    Mean-reversion strategies pass an explicit k_tp."""
    s = 1 if side == "long" else -1
    out = {"sl": entry - s * k_sl * atr_val, "risk_per_unit": k_sl * atr_val}
    if k_tp is not None:
        out["tp"] = entry + s * k_tp * atr_val
    return out


def time_stop_hit(bars_in_trade: int, max_bars: int,
                  unrealized_R: float, min_progress_R: float = 0.0) -> bool:
    """Exit if the trade went nowhere after max_bars (degraded expectancy)."""
    return bars_in_trade >= max_bars and unrealized_R <= min_progress_R
