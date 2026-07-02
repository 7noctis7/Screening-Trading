import sys; sys.path.insert(0, ".")
import numpy as np, pandas as pd
from packages.testing.certification import certify_indicator, certify_ohlcv

rng = np.random.default_rng(11)
n = 300
close = pd.Series(100 * np.exp(np.cumsum(rng.normal(0, 0.01, n))))
df = pd.DataFrame({"close": close})
df["high"] = df["close"] * (1 + abs(rng.normal(0, 0.004, n)))
df["low"] = df["close"] * (1 - abs(rng.normal(0, 0.004, n)))
df["open"] = df["close"].shift(1).fillna(df["close"])
df.index = pd.date_range("2025-01-01", periods=n, freq="D", tz="UTC")

sma20        = lambda d: d["close"].rolling(20).mean()                # clean
centered_ma  = lambda d: d["close"].rolling(20, center=True).mean()   # LEAK (uses future)
zscore_full  = lambda d: (d["close"] - d["close"].mean()) / d["close"].std()  # LEAK (full-sample norm)
future_shift = lambda d: d["close"].shift(-1).rolling(5).mean()       # LEAK (negative shift)

r_ok = certify_indicator(sma20, df)
assert r_ok["certified"], r_ok
for name, bad in [("centered_ma", centered_ma), ("zscore_full", zscore_full), ("future_shift", future_shift)]:
    r = certify_indicator(bad, df)
    assert not r["certified"] and not r["checks"]["no_lookahead"][0], (name, r)
    print(f"  {name:13s} -> REJECTED: {r['checks']['no_lookahead'][1][:60]}")

r_src = certify_ohlcv(df)
assert r_src["certified"], r_src
bad_df = df.copy(); bad_df.iloc[50, bad_df.columns.get_loc("low")] = bad_df.iloc[50]["high"] * 2
assert not certify_ohlcv(bad_df)["certified"]
print("  SMA20 clean  -> CERTIFIED | OHLCV clean -> CERTIFIED | OHLCV corrompu -> REJECTED")
print("HARNESS: ALL CHECKS PASSED")
