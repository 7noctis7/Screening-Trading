"""make sensitivity — les seuils main-tunés sont-ils ROBUSTES ? (audit #4)

(1) Screening : on perturbe chaque seuil dur (±) et on mesure la stabilité Jaccard de
    la sélection top-N. Un seuil fragile change radicalement la sélection.
(2) Régime : on perturbe les seuils du gate (dd_hard/dd_soft/g_dist/g_below) et on
    mesure la dérive moyenne d'exposition sur un proxy marché (QQQ).

  make sensitivity
  make sensitivity ARGS="--symbols AAPL,MSFT,NVDA,... --bench QQQ"
"""

from __future__ import annotations

import argparse
import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_BASKET = ("AAPL,MSFT,NVDA,GOOGL,AMZN,META,AVGO,TSLA,JPM,XOM,WMT,UNH,V,MA,COST,"
           "HD,PG,JNJ,CRM,AMD,NFLX,ADBE,CROX,ELF,CELH,RMBS,AAON,SPSC,BOOT,SHAK")
# Perturbations relatives de chaque seuil numérique (audit de sur-optimisation).
_PERTURB = {"dollar_volume": (0.5, 2.0), "drawdown_from_high": (1.5, 0.5),
            "ret_12m_hi": (0.75, 1.25)}


def _panel(symbols: list[str]) -> dict:
    from packages.data.price_loader import load_bars
    panel = {}
    for s in symbols:
        b = load_bars(s, years=3)
        if len(b) >= 260:
            panel[s] = b
    return panel


def _selected(cfg: dict, panel: dict) -> list[str]:
    from packages.screening.engine import ScreeningEngine
    return [r.symbol for r in ScreeningEngine(cfg).screen(panel)]


def _variant(base_cfg: dict, metric: str, factor: float, hi: bool = False) -> dict:
    cfg = copy.deepcopy(base_cfg)
    for f in cfg.get("filters", []):
        if f["metric"] != metric:
            continue
        if isinstance(f["value"], list):
            f["value"][1] = round(f["value"][1] * factor, 4)   # borne haute (ret_12m)
        else:
            f["value"] = round(f["value"] * factor, 4)
    return cfg


def _screen_sensitivity(panel: dict) -> int:
    import yaml

    from packages.research.sensitivity import selection_stability
    base_cfg = yaml.safe_load((ROOT / "config" / "screening.yaml").read_text("utf-8"))
    baseline = _selected(base_cfg, panel)
    if len(baseline) < 3:
        print(f"  ⚠ baseline trop petite ({len(baseline)}) — élargis --symbols.")
        return 0
    print(f"\nScreening · baseline {len(baseline)} retenus / {len(panel)} actifs")
    worst = 1.0
    for metric, (lo, hi) in (("dollar_volume", _PERTURB["dollar_volume"]),
                             ("drawdown_from_high", _PERTURB["drawdown_from_high"]),
                             ("ret_12m", _PERTURB["ret_12m_hi"])):
        variants = [_selected(_variant(base_cfg, metric, lo), panel),
                    _selected(_variant(base_cfg, metric, hi), panel)]
        st = selection_stability(baseline, variants)
        worst = min(worst, st["jaccard_min"])
        flag = "✅ stable" if st["stable"] else "⚠ FRAGILE"
        print(f"  {metric:<20} Jaccard min {st['jaccard_min']:.2f} "
              f"(±perturbation) → {flag}")
    print(f"  → pire stabilité : {worst:.2f} "
          f"({'robuste' if worst >= 0.7 else 'seuils fragiles à revoir'})")
    return 0


def _regime_sensitivity(bench: str) -> int:
    import numpy as np

    from packages.data.price_loader import load_bars
    from packages.research.sensitivity import regime_exposure_shift
    bars = load_bars(bench, years=5)
    if len(bars) < 260:
        print(f"  ⚠ proxy {bench} indisponible.")
        return 0
    mkt = np.array([b.close for b in bars], float)
    base = {"dd_hard": -0.15, "dd_soft": -0.10, "g_dist": 0.6, "g_below": 0.2}
    print(f"\nRégime · proxy {bench} · {len(mkt)} barres")
    for name, pert in (("dd_hard -0.20", {**base, "dd_hard": -0.20}),
                       ("dd_soft -0.07", {**base, "dd_soft": -0.07}),
                       ("g_dist 0.5", {**base, "g_dist": 0.5}),
                       ("g_below 0.3", {**base, "g_below": 0.3})):
        r = regime_exposure_shift(mkt, base, pert)
        flag = "✅ stable" if r["stable"] else "⚠ sensible"
        print(f"  {name:<16} dérive expo moy {r['mean_exposure_shift']:.3f} → {flag}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Sensibilité seuils screening + régime")
    ap.add_argument("--symbols", default=_BASKET)
    ap.add_argument("--bench", default="QQQ")
    a = ap.parse_args()
    syms = [s.strip().upper() for s in a.symbols.split(",") if s.strip()]
    print(f"Chargement {len(syms)} actifs (prix réels / yfinance)…")
    panel = _panel(syms)
    if len(panel) < 5:
        print(f"❌ panel trop petit ({len(panel)}). Réseau/base ?")
        return 1
    _screen_sensitivity(panel)
    _regime_sensitivity(a.bench)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
