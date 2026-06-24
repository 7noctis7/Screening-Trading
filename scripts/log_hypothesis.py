"""make log-alpha — enregistre un essai d'hypothèse d'alpha (ledger anti p-hacking).

Usage :
  python scripts/log_hypothesis.py --facteur momentum --classe equity,crypto \\
      --horizon swing --dsr 0.01 --pbo 0.5 --sharpe 2.44 --maxdd -0.09 \\
      --statut en_test --these "Momentum 12-1 sur l'univers liquide"

Chaque appel ajoute UNE ligne au JSONL → trace de tous les essais (le `N` qui
déflate le Sharpe). Affiche ensuite le compteur d'essais et le résumé.
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    from packages.research.ledger import append_record, summary, trial_count

    ap = argparse.ArgumentParser(description="Logue un essai d'hypothèse d'alpha")
    ap.add_argument("--facteur", required=True)
    ap.add_argument("--classe", default="", help="liste séparée par des virgules")
    ap.add_argument("--horizon", default="swing")
    ap.add_argument("--dsr", type=float, default=None)
    ap.add_argument("--pbo", type=float, default=None)
    ap.add_argument("--sharpe", type=float, default=None)
    ap.add_argument("--maxdd", type=float, default=None)
    ap.add_argument("--statut", default="en_test",
                    choices=["hypothese", "en_test", "rejete", "promu"])
    ap.add_argument("--these", default="")
    a = ap.parse_args()

    rec = {
        "date": datetime.now(UTC).date().isoformat(),
        "facteur": a.facteur,
        "classe": [c.strip() for c in a.classe.split(",") if c.strip()],
        "horizon": a.horizon, "dsr": a.dsr, "pbo": a.pbo,
        "sharpe": a.sharpe, "maxdd": a.maxdd, "statut": a.statut, "these": a.these,
    }
    append_record(rec)
    s = summary()
    print(f"✅ Essai enregistré ({a.facteur}). Total essais N={trial_count()} · "
          f"robustes={s['n_robust']} · meilleur DSR={s['best_dsr']}")
    print("⚠ N ↑ → le seuil DSR se relève (déflation multi-essais).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
