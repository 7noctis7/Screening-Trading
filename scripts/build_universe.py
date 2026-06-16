"""Construit l'univers depuis toutes les sources et persiste un snapshot daté.

  python scripts/build_universe.py            # offline (sources statiques)
  python scripts/build_universe.py --network  # complet (Wikipédia + listings + CoinGecko)

Offline → ~325 instruments (seeds). En ligne → +S&P500/Nasdaq/SBF120/FTSE/MIB/
Nikkei/KOSPI/CSI300 + listings COMPLETS NYSE+Nasdaq (milliers) + crypto live.
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from packages.common import due_for_rebuild, load_yaml  # noqa: E402
from packages.data.universe import UniverseBuilder  # noqa: E402
from packages.storage import UniverseRepository  # noqa: E402


def main() -> int:
    allow_network = "--network" in sys.argv
    force = "--force" in sys.argv
    db = ROOT / "data" / "universe.db"
    db.parent.mkdir(exist_ok=True)

    cadence = load_yaml(ROOT / "config" / "universe.yaml").get("rebuild_cadence_days", 30)
    last = UniverseRepository(db).latest_date()
    if not force and not due_for_rebuild(last, cadence):
        print(f"Univers à jour (dernier snapshot {last}, cadence {cadence}j). "
              f"--force pour forcer.")
        return 0

    res = UniverseBuilder(ROOT / "config" / "universe.yaml",
                          allow_network=allow_network).build()
    repo = UniverseRepository(db)
    as_of = repo.save_snapshot(res.instruments, res.as_of)

    by_class = Counter(i.asset_class.value for i in res.instruments)
    print("\n" + "=" * 50)
    print(f" UNIVERS — snapshot {as_of}  (network={allow_network})")
    print("=" * 50)
    print(f" Total instruments : {len(res.instruments)}")
    for k, v in sorted(by_class.items(), key=lambda x: -x[1]):
        print(f"   {k:12s} {v}")
    print(f" Sources actives   : {len(res.per_source)}")
    if res.skipped:
        print(f" Sources sautées   : {', '.join(res.skipped)}")
        if not allow_network:
            print("   → relancer avec --network pour les inclure")
    print(f" Persisté → {db}")
    print("=" * 50 + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
