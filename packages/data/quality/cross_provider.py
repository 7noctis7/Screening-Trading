"""Cross-provider OHLCV validation: same series from two sources, diffed.
Divergence beyond threshold -> quarantine + alert. Bad prints are the #1
silent signal-killer."""
from __future__ import annotations

import pandas as pd


def diff_report(a: pd.DataFrame, b: pd.DataFrame, col: str = "close",
                rel_threshold: float = 0.002) -> dict:
    """a, b: OHLCV frames indexed by UTC timestamp."""
    j = a[[col]].join(b[[col]], how="inner", lsuffix="_a", rsuffix="_b").dropna()
    if j.empty:
        return {"overlap": 0, "flagged": 0, "quarantine": True,
                "note": "no overlapping timestamps - alignment bug?"}
    rel = (j[f"{col}_a"] - j[f"{col}_b"]).abs() / j[f"{col}_b"]
    flagged = rel[rel > rel_threshold]
    return {"overlap": len(j), "flagged": int(len(flagged)),
            "flag_rate": float(len(flagged) / len(j)),
            "worst_rel_diff": float(rel.max()),
            "flagged_ts": [str(t) for t in flagged.index[:10]],
            "quarantine": bool(len(flagged) / len(j) > 0.01)}
