"""Lit le dernier IC du classement tradé. Ne remesure pas, ne consigne pas.

Codes : 0 OUVERT, 2 UNCALIBRATED, 3 GELÉ.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    from packages.research.gel_ic import lire
    v = lire(ROOT / "out" / "ic_classement.json")
    print(v["ligne"])
    return {"OUVERT": 0, "UNCALIBRATED": 2, "GELE": 3}.get(v["statut"], 2)


if __name__ == "__main__":
    raise SystemExit(main())
