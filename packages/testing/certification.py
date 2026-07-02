"""Generic certification harness: property tests that EVERY component must
pass before entering the system. No component is trusted; every component
is proven. Used by /certify and by CI."""
from __future__ import annotations

from typing import Callable

import numpy as np
import pandas as pd

Verdict = tuple[bool, str]


# ---------- INDICATORS ----------
def no_lookahead(fn: Callable[[pd.DataFrame], pd.Series], df: pd.DataFrame,
                 n_points: int = 12, rtol: float = 1e-9) -> Verdict:
    """Truncation invariance — THE anti-leak test. The value at t must be
    identical whether computed on data[:t] or on the full sample. Any
    indicator using future info (negative shift, centered window, full-sample
    normalization) fails here."""
    full = fn(df)
    T = len(df)
    for t in np.linspace(T // 2, T - 1, n_points, dtype=int):
        trunc = fn(df.iloc[: t + 1])
        a, b = full.iloc[t], trunc.iloc[-1]
        if pd.isna(a) and pd.isna(b):
            continue
        if pd.isna(a) != pd.isna(b) or not np.isclose(a, b, rtol=rtol):
            return False, f"LOOK-AHEAD at t={t}: full={a!r} vs truncated={b!r}"
    return True, "truncation-invariant"


def deterministic(fn: Callable, df: pd.DataFrame, runs: int = 3) -> Verdict:
    outs = [fn(df) for _ in range(runs)]
    for o in outs[1:]:
        if not outs[0].equals(o):
            return False, "non-deterministic output across identical runs"
    return True, "deterministic"


def sane_output(fn: Callable, df: pd.DataFrame) -> Verdict:
    out = fn(df)
    if len(out) != len(df):
        return False, f"length {len(out)} != input {len(df)} (index misalignment)"
    if np.isinf(out.dropna()).any():
        return False, "contains +/-inf"
    if out.notna().all() and len(df) > 5:
        return False, "no warmup NaNs at all - suspicious (window ignored?)"
    return True, "aligned, finite, warmup respected"


def certify_indicator(fn: Callable, df: pd.DataFrame) -> dict:
    checks = {"no_lookahead": no_lookahead(fn, df),
              "deterministic": deterministic(fn, df),
              "sane_output": sane_output(fn, df)}
    return {"certified": all(v[0] for v in checks.values()), "checks": checks}


# ---------- DATA SOURCES (OHLCV) ----------
def certify_ohlcv(df: pd.DataFrame) -> dict:
    c: dict[str, Verdict] = {}
    c["utc_index"] = (getattr(df.index, "tz", None) is not None
                      and str(df.index.tz) == "UTC", f"tz={getattr(df.index,'tz',None)}")
    c["unique_sorted"] = (df.index.is_unique and df.index.is_monotonic_increasing,
                          "index unique+sorted" if df.index.is_unique else "duplicates!")
    hl = (df["high"] >= df["low"]).all()
    c["high_ge_low"] = (bool(hl), "ok" if hl else f"{(df['high']<df['low']).sum()} bars high<low")
    inside = df["close"].between(df["low"], df["high"]).all()
    c["close_in_range"] = (bool(inside), "ok" if inside else "close outside [low,high]")
    pos = (df[["open", "high", "low", "close"]] > 0).all().all()
    c["positive_prices"] = (bool(pos), "ok" if pos else "non-positive prices")
    jumps = df["close"].pct_change().abs()
    nj = int((jumps > 0.5).sum())
    c["no_extreme_jumps"] = (nj == 0, "ok" if nj == 0 else f"{nj} bars |ret|>50% - splits unadjusted?")
    return {"certified": all(v[0] for v in c.values()), "checks": c}
