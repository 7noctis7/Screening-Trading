"""Démo pipeline ML (offline) — triple-barrier + features point-in-time + CV purgée.

  python scripts/demo_ml.py

Montre la boucle López de Prado : labeling triple-barrière → features (technique gold +
macro point-in-time) → CV PURGÉE & embargo → modèles → champion/challenger. Sur données
synthétiques l'accuracy OOS reste ~50% (aucun edge fabriqué — c'est voulu).
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from packages.common import load_yaml  # noqa: E402
from packages.data import data_providers  # noqa: E402
from packages.ml import (  # noqa: E402
    FeatureBuilder, ModelRegistry, ewm_volatility, make_model, meta_labels,
    purged_cv_score, triple_barrier,
)
from packages.regime import synthetic_macro  # noqa: E402
from packages.storage import FeatureStore, MacroStore, materialize_indicators  # noqa: E402


def main() -> int:
    start = datetime(2019, 1, 1, tzinfo=timezone.utc)
    bars = data_providers.create("synthetic", seed=7, drift=0.05).fetch_ohlcv(
        "AAPL", "1d", start, start + timedelta(days=900))
    close = np.array([b.close for b in bars])
    ts = [b.ts for b in bars]

    fs = FeatureStore(":memory:")
    materialize_indicators(bars, fs, load_yaml(ROOT / "config" / "features.yaml")["indicators"])
    ms = MacroStore(":memory:")
    ms.upsert(synthetic_macro(start, months=36))

    entries = list(range(250, len(bars) - 25, 3))
    labels = triple_barrier(close, entries, pt=2, sl=2, vol=ewm_volatility(close), horizon=20)
    y = meta_labels(labels, side=1)
    X, names = FeatureBuilder(fs, ms, macro_series=("T10Y3M", "ISM", "VIXCLS")).build(
        "AAPL", "1d", [ts[e] for e in entries])
    t0 = np.array(entries)
    t1 = np.array([lab.exit_idx for lab in labels])

    print("\n" + "=" * 60)
    print(" PIPELINE ML — triple-barrier + CV purgée (López de Prado)")
    print("=" * 60)
    counts = {v: int((np.array([lab.label for lab in labels]) == v).sum()) for v in (-1, 0, 1)}
    print(f" Entrées étiquetées : {len(entries)}  (profit={counts[1]} stop={counts[-1]} temps={counts[0]})")
    print(f" Méta-label gagnants: {y.mean():.0%}")
    print(f" Matrice features   : {X.shape}  ({len(names)} features dont macro point-in-time)")
    reg = ModelRegistry()
    for kind in ("logit", "sklearn"):
        sc = purged_cv_score(lambda: make_model(kind), X, y, t0, t1, n_splits=5)  # noqa: B023
        mean = float(np.mean(sc)) if sc else 0.0
        d = reg.consider(kind, None, mean)
        print(f"   {kind:8s} accuracy OOS purgée = {mean:.3f} → {d.reason}")
    print(f" Champion retenu    : {reg.champion}")
    print(" (OOS ~50% = aucun alpha sur du synthétique : garde-fou anti-surapprentissage)")
    print("=" * 60 + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
