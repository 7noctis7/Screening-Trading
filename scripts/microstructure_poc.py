#!/usr/bin/env python3
"""POC microstructure crypto — OFI + vPIN en direct (Binance REST, gratuit, sans clé).

Tourne sur ton Mac (always-on). Échantillonne le carnet L2 + trades agrégés ~1×/s,
calcule l'Order Flow Imbalance cumulé et le vPIN (toxicité). Signal de RECHERCHE : à
passer au gate avant tout câblage. WebSocket = upgrade. Ctrl+C arrête.

  make microstructure-poc SYM=BTCUSDT
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from packages.research.microstructure import ofi_series, vpin  # noqa: E402

_DEPTH = "https://api.binance.com/api/v3/depth?symbol={s}&limit=5"
_TRADES = "https://api.binance.com/api/v3/aggTrades?symbol={s}&limit=1000"


def _get(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": "quant-terminal/1.0"})
    with urllib.request.urlopen(req, timeout=8) as r:  # noqa: S310
        return json.loads(r.read().decode())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sym", default="BTCUSDT")
    ap.add_argument("--secs", type=int, default=120, help="durée d'échantillonnage")
    a = ap.parse_args()
    book: deque = deque(maxlen=600)
    print(f"Échantillonnage microstructure {a.sym} ({a.secs}s)… Ctrl+C pour arrêter.")
    t0 = time.time()
    try:
        while time.time() - t0 < a.secs:
            d = _get(_DEPTH.format(s=a.sym))
            pb, qb = float(d["bids"][0][0]), float(d["bids"][0][1])
            pa, qa = float(d["asks"][0][0]), float(d["asks"][0][1])
            book.append((pb, qb, pa, qa))
            tr = _get(_TRADES.format(s=a.sym))
            prices = [float(x["p"]) for x in tr]
            vols = [float(x["q"]) for x in tr]
            vol_tot = sum(vols)
            vp = vpin(prices, vols, bucket=max(1e-6, vol_tot / 50), n_buckets=20)
            ofi = ofi_series(list(book))
            vps = vp.get("vpin") if vp.get("available") else "n/d"
            print(f"  OFI({len(book)}) = {ofi:+.3f} · vPIN = {vps} "
                  f"· spread = {pa - pb:.2f}")
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("\narrêté.")
    print("\nLecture : OFI>0 = pression acheteuse · vPIN↑ = flux toxique (risque de choc).")
    print("⚠️ Signal de recherche — à valider au gate (placebo/DSR/PBO/sabotage).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
