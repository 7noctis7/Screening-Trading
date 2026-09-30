"""Journal de trades en mémoire (v1). Miroir de la table du Module 8.

Le snapshot des features à l'entrée est conservé → réapprentissage ML possible.
À remplacer en P1 par un repository persistant (DuckDB/SQLAlchemy).
"""

from __future__ import annotations

import csv
from pathlib import Path

from packages.core.models import TradeRecord


class TradeJournal:
    def __init__(self) -> None:
        self._trades: list[TradeRecord] = []

    def append(self, trade: TradeRecord, *, legacy: bool = False) -> None:
        # `legacy` accepté pour la parité d'interface avec SqliteTradeJournal (no-op ici).
        self._trades.append(trade)

    def all(self) -> list[TradeRecord]:
        return list(self._trades)

    def pnls(self) -> list[float]:
        return [t.pnl_net for t in self._trades if t.pnl_net is not None]

    def to_csv(self, path: str | Path) -> None:
        if not self._trades:
            return
        fields = ["id", "instrument", "side", "strategy", "regime", "entry_ts",
                  "entry_price", "exit_ts", "exit_price", "qty", "pnl_net",
                  "pnl_pct", "r_multiple", "is_win", "entry_reason", "exit_reason",
                  "order_id", "fill_id", "qty_filled",
                  "ts_arrival", "ts_send", "ts_fill",
                  "P_arrival", "P_fill",
                  "P_mid_arrival", "P_mid_fill", "P_mid_fill_h",
                  "P_bid_fill", "P_ask_fill",
                  "fee_comm", "fee_funding",
                  "impact_horizon", "bench_quality", "tca_variant"]
        with Path(path).open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            for t in self._trades:
                w.writerow({
                    "id": t.id, "instrument": t.instrument, "side": t.side.value,
                    "strategy": t.strategy, "regime": t.regime,
                    "entry_ts": t.entry_ts.isoformat(), "entry_price": round(t.entry_price, 4),
                    "exit_ts": t.exit_ts.isoformat() if t.exit_ts else "",
                    "exit_price": round(t.exit_price, 4) if t.exit_price else "",
                    "qty": round(t.qty, 6), "pnl_net": round(t.pnl_net or 0, 2),
                    "pnl_pct": round(t.pnl_pct or 0, 4), "r_multiple": round(t.r_multiple or 0, 2),
                    "is_win": t.is_win, "entry_reason": t.entry_reason,
                    "exit_reason": t.exit_reason,
                    "order_id": t.order_id or "",
                    "fill_id": t.fill_id or "",
                    "qty_filled": "" if t.qty_filled is None else t.qty_filled,
                    "ts_arrival": t.ts_arrival.isoformat() if t.ts_arrival else "",
                    "ts_send": t.ts_send.isoformat() if t.ts_send else "",
                    "ts_fill": t.ts_fill.isoformat() if t.ts_fill else "",
                    "P_arrival": "" if t.P_arrival is None else t.P_arrival,
                    "P_fill": "" if t.P_fill is None else t.P_fill,
                    "P_mid_arrival": "" if t.P_mid_arrival is None else t.P_mid_arrival,
                    "P_mid_fill": "" if t.P_mid_fill is None else t.P_mid_fill,
                    "P_mid_fill_h": "" if t.P_mid_fill_h is None else t.P_mid_fill_h,
                    "P_bid_fill": "" if t.P_bid_fill is None else t.P_bid_fill,
                    "P_ask_fill": "" if t.P_ask_fill is None else t.P_ask_fill,
                    "fee_comm": "" if t.fee_comm is None else t.fee_comm,
                    "fee_funding": "" if t.fee_funding is None else t.fee_funding,
                    "impact_horizon": t.impact_horizon or "",
                    "bench_quality": t.bench_quality or "",
                    "tca_variant": t.tca_variant or "",})
