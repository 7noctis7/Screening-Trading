"""Attribution de performance — décompose le P&L par clé (actif/classe/stratégie/régime)."""

from __future__ import annotations


def attribute(trades: list, key: str = "strategy") -> dict[str, float]:
    out: dict[str, float] = {}
    for t in trades:
        k = getattr(t, key, None)
        k = k.value if hasattr(k, "value") else (k or "?")
        out[str(k)] = out.get(str(k), 0.0) + float(getattr(t, "pnl_net", 0.0) or 0.0)
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))
