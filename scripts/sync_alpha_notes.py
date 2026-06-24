"""make sync-alphas — propage le ledger (research/hypotheses.jsonl) vers le frontmatter
des notes vault/08_Alphas/ (dsr/pbo/sharpe/maxdd). À lancer après `make log-alpha`.
`calibrate-preset` le fait déjà tout seul ; ce script sert à re-synchroniser à la main.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    from packages.research.ledger import summary, sync_notes_frontmatter
    n = sync_notes_frontmatter()
    s = summary()
    print(f"✅ {n} note(s) 08_Alphas/ synchronisée(s) depuis le ledger "
          f"(N={s['n_trials']} essais · meilleur DSR={s['best_dsr']}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
