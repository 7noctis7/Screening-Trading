"""Ingestion des CAPITALISATIONS BOURSIÈRES (market cap) → data/market_caps.json.

Récupère via yfinance le nombre d'ACTIONS en circulation (historique si dispo, sinon courant)
pour les plus grosses sociétés US de ton univers, afin que le cœur « top-10 méga-caps » soit
classé ET pondéré par la VRAIE market cap (et non le proxy dollar-volume). Stockage SIDECAR
non destructif (n'écrit JAMAIS dans YAHOO.db, ouverte en lecture seule).

  export QUANT_PRICE_DB=/chemin/YAHOO.db
  python scripts/ingest_market_cap.py            # top 200 sociétés US par liquidité
  python scripts/ingest_market_cap.py --top 100  # restreint au Nasdaq-100 « de facto »
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=200, help="nb de sociétés (par liquidité) à couvrir")
    a = ap.parse_args()

    import numpy as np

    from apps.api.snapshot import (_HISTORY_DAYS, _load_prices, _sector_of, _seed_universe,
                                   datetime, timedelta, timezone)
    from packages.data.market_cap import market_cap_path
    from packages.execution.routing import is_tradeable

    inst = _seed_universe()
    so = {m["symbol"]: _sector_of(m) for m in inst}
    ac = {m["symbol"]: m.get("asset_class", "equity") for m in inst}
    end = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    start = end - timedelta(days=_HISTORY_DAYS)
    data, mode, _real = _load_prices(inst, so, start, end, 7)

    # candidats = sociétés US négociables (pas d'ETF), classées par liquidité récente
    cand = [s for s, b in data.items()
            if b and len(b) > 60 and ac.get(s, "equity") in ("equity", "")
            and is_tradeable(s, ac.get(s, "equity"))]
    dvol = {s: float(np.mean([bb.close * getattr(bb, "volume", 0.0) for bb in data[s][-60:]]))
            for s in cand}
    cand = sorted(cand, key=lambda s: dvol.get(s, 0.0), reverse=True)[:a.top]
    print(f"Mode données : {mode} · {len(cand)} sociétés US à couvrir (top liquidité)\n")

    try:
        import yfinance as yf
    except Exception:  # noqa: BLE001
        print("yfinance indisponible — installe-le (uv pip install yfinance)."); return

    out: dict = {}
    s_iso = start.date().isoformat()
    e_iso = end.date().isoformat()
    ok_hist = ok_cur = 0
    for i, s in enumerate(cand, 1):
        rec: dict = {}
        try:
            tk = yf.Ticker(s)
            try:
                ser = tk.get_shares_full(start=s_iso, end=e_iso)        # actions historiques
                if ser is not None and len(ser) > 0:
                    hist = [[str(d)[:10], float(v)] for d, v in ser.items() if v and float(v) > 0]
                    if hist:
                        rec["history"] = hist
                        ok_hist += 1
            except Exception:  # noqa: BLE001
                pass
            if "history" not in rec:
                cur = None
                try:
                    cur = getattr(tk.fast_info, "shares", None)
                except Exception:  # noqa: BLE001
                    cur = None
                cur = cur or (tk.info or {}).get("sharesOutstanding")
                if cur:
                    rec["current"] = float(cur)
                    ok_cur += 1
        except Exception:  # noqa: BLE001
            pass
        if rec:
            out[s] = rec
        if i % 25 == 0:
            print(f"  … {i}/{len(cand)} (hist {ok_hist} · courant {ok_cur})")

    if not out:
        print("Aucune market cap récupérée (réseau ? quota yfinance ?)."); return
    p = market_cap_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out))
    print(f"\n✅ {len(out)} sociétés écrites → {p}  (historique: {ok_hist} · courant seul: {ok_cur})")
    print("   Le cœur « top-10 méga-caps » est maintenant classé & pondéré par market cap réelle.")
    print("   Relance le site (make api) pour prise en compte.")


if __name__ == "__main__":
    main()
