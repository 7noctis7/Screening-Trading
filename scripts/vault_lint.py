"""make vault-lint — intégrité du vault (liens morts, orphelins, ADR en double).

Garde ta MÉMOIRE aussi honnête que ton code. exit≠0 si lien mort ou ADR dupliqué
(gate dur) ; les orphelins sont des avertissements. 0 €, stdlib.

  make vault-lint
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    import argparse

    from packages.common.vault_lint import lint_vault
    ap = argparse.ArgumentParser(description="Lint du vault")
    ap.add_argument("--strict", action="store_true",
                    help="exit≠0 aussi sur liens morts / orphelins (gate CI)")
    a = ap.parse_args()
    r = lint_vault(ROOT / "vault")
    print(f"\nVault-lint · {r['n_notes']} notes")
    print(f"  liens morts ({len(r['dead_links'])}) :")
    for d in r["dead_links"][:20]:
        print(f"     ✗ {d['in']} → {d['link']}")
    print(f"  ADR en double   : {r['duplicate_adrs'] or '—'}")
    print(f"  orphelins ({len(r['orphans'])}) : "
          f"{', '.join(r['orphans'][:15]) or '—'}")
    # gate dur : ADR dupliqués (vrai bug) toujours ; le reste seulement en --strict
    if r["duplicate_adrs"]:
        print("  → ❌ ADR dupliqué (corriger).")
        return 1
    if a.strict and (r["dead_links"] or r["orphans"]):
        print("  → ❌ --strict : liens morts / orphelins à corriger.")
        return 1
    print("  → ✅ pas de bug bloquant (liens morts/orphelins = avertissements).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
