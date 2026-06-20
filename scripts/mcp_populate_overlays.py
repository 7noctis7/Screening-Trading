"""Peuple les overlays (cônes VaR/EVT + marqueurs réels + blackouts résultats) depuis l'API.

Découplé du cœur : lit l'API HTTP du terminal et écrit l'OverlayStore lu par le front.
Usage : python scripts/mcp_populate_overlays.py [--base http://localhost:8000] [--var 95|99] [--lookback 21]
À lancer ponctuellement ou en cron, API démarrée.  (cf. make mcp-overlays)
"""

from __future__ import annotations

import argparse
import json

from packages.mcp_tradingview.risk_overlays import Z_VAR95, Z_VAR99, populate_from_api


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:8000")
    ap.add_argument("--var", choices=["95", "99"], default="95")
    ap.add_argument("--lookback", type=int, default=21)
    ap.add_argument("--evt-mult", type=float, default=1.15)
    a = ap.parse_args()
    res = populate_from_api(base_url=a.base, z=Z_VAR99 if a.var == "99" else Z_VAR95,
                            lookback=a.lookback, evt_mult=a.evt_mult)
    print(json.dumps(res, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
