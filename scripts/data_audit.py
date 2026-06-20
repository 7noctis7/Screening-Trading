"""Audit PwC des bases de prix (complétude / exactitude / point-in-time). À lancer en CI ou cron.

  python scripts/data_audit.py            # audite data/market.db + crypto.db
  python scripts/data_audit.py --strict   # code de sortie ≠ 0 si anomalie CRITIQUE (gate CI)

NON destructif (lecture seule). Best-effort : si une base est absente, on l'ignore proprement.
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true", help="exit 1 si anomalie critique (gate CI)")
    ap.add_argument("--dbs", nargs="*", default=["market", "crypto"])
    a = ap.parse_args()
    from packages.data.audit import assert_integrity, audit_and_report, DataIntegrityError
    from packages.data.engine import read_prices_rows

    critical_total = 0
    for db in a.dbs:
        rows = read_prices_rows(db)
        if not rows:
            print(f"· {db}.db : absente ou vide — ignorée")
            continue
        by: dict[str, list] = defaultdict(list)
        for r in rows:
            by[r.get("symbol")].append(r)
        rep = audit_and_report(by)
        c = rep.counts()
        print(f"· {db}.db : {rep.n_symbols} symboles · {rep.n_bars} barres · "
              f"critiques {c['critical']} · majeurs {c['major']} · warnings {c['warning']}")
        for an in rep.critical[:10]:
            print(f"    🔴 {an.symbol} · {an.kind} · {an.detail}")
        critical_total += c["critical"]
        if a.strict:
            try:
                assert_integrity(rep)
            except DataIntegrityError as e:
                print(f"❌ {e}")
    if a.strict and critical_total:
        sys.exit(1)
    print(f"Audit terminé · {critical_total} anomalie(s) critique(s).")


if __name__ == "__main__":
    main()
