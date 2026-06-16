"""Démo macro & régime point-in-time (offline, synthétique).

  python scripts/demo_macro_regime.py

Montre : ingestion macro vintage → MacroStore → régime quotidien point-in-time →
cartographie d'impact (exposition + inclinaisons de facteurs) + surprises éco.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from packages.common import load_yaml  # noqa: E402
from packages.core.models import EconomicRelease  # noqa: E402
from packages.regime import (  # noqa: E402
    MacroImpactMap, MacroRegimeClassifier, surprise_index, synthetic_macro,
)
from packages.storage import MacroStore  # noqa: E402


def main() -> int:
    ms = MacroStore(":memory:")
    ms.upsert(synthetic_macro(datetime(2021, 1, 1, tzinfo=timezone.utc), months=48))
    clf = MacroRegimeClassifier(ms)
    imp = MacroImpactMap(load_yaml(ROOT / "config" / "macro_impact.yaml"))

    print("\n" + "=" * 64)
    print(" MACRO & RÉGIME — point-in-time (vintages + délai de publication)")
    print("=" * 64)
    print(f" Observations macro : {ms.count()}")
    print(f" {'date':12s} {'cycle':10s} {'risk':9s} {'curve':>6s} {'pmi':>4s} "
          f"{'vix':>4s} {'expo':>5s}")
    for ds in ("2021-09-15", "2022-06-15", "2023-01-15", "2023-09-15", "2024-06-15"):
        t = datetime.fromisoformat(ds).replace(tzinfo=timezone.utc)
        rs = clf.classify(t)
        expo = imp.exposure_multiplier(rs)
        print(f" {ds:12s} {rs.cycle.value:10s} {rs.risk_mode.value:9s} "
              f"{rs.extras['curve_2s10s']:+6.2f} {rs.extras['pmi']:4.0f} "
              f"{rs.vix:4.0f} ×{expo:.2f}")

    # surprises éco
    rel = [EconomicRelease("CPIAUCSL", datetime(2024, 6, 1, tzinfo=timezone.utc), 3.4, 3.1, 0.2),
           EconomicRelease("ISM", datetime(2024, 6, 3, tzinfo=timezone.utc), 48, 50, 1.0)]
    s = surprise_index(rel, datetime(2024, 6, 15, tzinfo=timezone.utc))
    print("\n Surprises éco (z, réalisé vs consensus) :")
    print(f"   inflation {s.get('inflation', 0):+.2f} | croissance {s.get('growth', 0):+.2f}")
    print(f"   → inclinaisons classes : {imp.class_tilts(s)}")
    print("=" * 64 + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
